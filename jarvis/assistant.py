"""Главный оркестратор: STT → wake word → роутер (локально) → Gemini (агент) → TTS."""
from __future__ import annotations

import random
import threading
from collections.abc import Callable, Iterable, Iterator

from .config import Config
from .llm import GeminiClient, QuotaExceeded
from .logger import get_logger
from .router import Router
from .skills import build_default_router
from .wakeword import WakeWordDetector

log = get_logger("assistant")

GREETINGS = [
    "Слушаю, сэр.",
    "Да, сэр?",
    "Я здесь.",
    "К вашим услугам.",
]

ACK_NO_COMMAND = [
    "Слушаю.",
    "Я готов.",
    "Чем могу помочь?",
]

NOT_UNDERSTOOD = [
    "Прошу прощения, не понял команду.",
    "Уточните, пожалуйста.",
    "Не разобрал, повторите.",
]

EXIT_PHRASES = (
    "выход", "хватит", "стоп джарвис", "завершить работу", "пока джарвис",
    "выключи себя", "отбой",
)


class _Speaker:  # protocol-like
    def speak(self, text: str) -> None: ...


def _default_open_settings(reason: str) -> None:
    """Fallback: открывает окно настроек в отдельном потоке (Tk-mainloop блокирует).

    GUI-режим подменяет этот callback своим (root.after), чтобы не создавать
    второй Tk root.
    """
    def _go():
        try:
            from .gui.settings import open_settings_dialog
            open_settings_dialog(reason=reason)
        except Exception as exc:  # pragma: no cover
            log.error("settings dialog failed: %s", exc)

    threading.Thread(target=_go, daemon=True).start()


class Assistant:
    def __init__(
        self,
        config: Config,
        speaker: _Speaker,
        wake_detector: WakeWordDetector,
        llm: GeminiClient | None = None,
        router: Router | None = None,
        open_settings: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config
        self.speaker = speaker
        self.wake = wake_detector
        self.llm = llm
        self.router = router or build_default_router(config)
        self._open_settings: Callable[[str], None] = open_settings or _default_open_settings

    def greet(self) -> None:
        if not self.config.gemini_api_key:
            self.speaker.speak("Джарвис на связи. API-ключ не задан — открываю настройки.")
            self._open_settings("Введи API-ключ Gemini, чтобы заработала «болталка» и агент-режим.")
        else:
            mode = "агент" if self.config.agent_mode else "только команды"
            self.speaker.speak(f"Джарвис на связи. Режим: {mode}.")

    def _ask_llm(self, text: str) -> str:
        if not self.llm or not self.llm.available:
            return ""
        try:
            return self.llm.ask(text)
        except QuotaExceeded:
            self.speaker.speak("Сэр, квота Gemini исчерпана. Открываю настройки — введите другой ключ.")
            self._open_settings("Квота API-ключа исчерпана. Введи новый ключ.")
            return ""

    def _handle(self, command: str) -> bool:
        """Обрабатывает одну команду. Возвращает False, если пора выйти."""
        text = command.strip().lower()
        if not text:
            self.speaker.speak(random.choice(ACK_NO_COMMAND))
            return True

        if any(ex in text for ex in EXIT_PHRASES):
            self.speaker.speak("Завершаю работу. До связи, сэр.")
            return False

        agent_mode_with_llm = (
            self.config.agent_mode and self.llm is not None and self.llm.available
        )

        # В агент-режиме Gemini — «мозг»: ему уходит ВСЁ. Локальный роутер только
        # как запасной (нет ключа, нет интернета, кончилась квота).
        if agent_mode_with_llm:
            answer = self._ask_llm(command)
            if answer:
                self.speaker.speak(answer)
                return True
            # LLM не ответил — пробуем локальный роутер как fallback.
            response = self.router.dispatch(text)
            if response is not None:
                if response:
                    self.speaker.speak(response)
                return True
            self.speaker.speak(random.choice(NOT_UNDERSTOOD))
            return True

        # Без агент-режима (или без ключа): сначала локальный роутер, потом LLM.
        response = self.router.dispatch(text)
        if response is not None:
            if response:
                self.speaker.speak(response)
            return True
        if self.llm and self.llm.available:
            answer = self._ask_llm(command)
            if answer:
                self.speaker.speak(answer)
                return True
        self.speaker.speak(random.choice(NOT_UNDERSTOOD))
        return True

    def run(self, phrases: Iterable[str] | Iterator[str]) -> None:
        for phrase in phrases:
            log.debug("получено: %s", phrase)
            command = self.wake.detect(phrase)
            if command is None:
                continue

            if not command:
                self.speaker.speak(random.choice(GREETINGS))
                continue

            if not self._handle(command):
                return
