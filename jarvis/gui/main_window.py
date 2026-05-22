"""Главное окно Jarvis — полноценный GUI с чатом, статусом и микрофоном."""
from __future__ import annotations

import contextlib
import queue
import random
import threading
import tkinter as tk
from collections.abc import Callable, Iterator
from tkinter import scrolledtext, ttk
from typing import Any

from ..assistant import EXIT_PHRASES, GREETINGS, Assistant
from ..config import Config
from ..llm import GeminiClient
from ..logger import get_logger
from ..wakeword import WakeWordDetector

# Короткие голосовые «подтверждения» перед тем как уйти в Gemini —
# чтобы пользователь слышал отклик сразу, а не молчание.
_ACKS = [
    "Принял, сэр.",
    "Понял, сэр.",
    "Секунду, сэр.",
    "Минутку.",
    "Работаю.",
]

log = get_logger("gui.main")


_STATUS_IDLE = "Готов"
_STATUS_LISTEN = "Слушаю…"
_STATUS_THINK = "Думаю…"
_STATUS_SPEAK = "Говорю…"
_STATUS_MIC_OFF = "Микрофон выключен"


class _GuiSpeaker:
    """Speaker-обёртка: реальный pyttsx3 + апдейт чата в Tk-потоке.

    Все запросы на озвучку сериализуются в одном фоновом потоке,
    чтобы pyttsx3 (SAPI5/COM) не падал от parallel-обращений.
    """

    def __init__(
        self,
        real_speaker: Any,
        on_text: Callable[[str], None],
        on_speak_state: Callable[[bool], None],
    ) -> None:
        self._real = real_speaker
        self._on_text = on_text
        self._on_speak_state = on_speak_state
        self._q: queue.Queue[str | None] = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True, name="jarvis-tts")
        self._thread.start()

    def speak(self, text: str) -> None:
        if not text:
            return
        # Сразу показываем в чате — пользователь видит ответ, пока TTS только готовится.
        with contextlib.suppress(Exception):
            self._on_text(text)
        self._q.put(text)

    def _worker(self) -> None:
        while True:
            item = self._q.get()
            if item is None:
                return
            try:
                self._on_speak_state(True)
                self._real.speak(item)
            except Exception as exc:  # pragma: no cover
                log.warning("TTS failed: %s", exc)
            finally:
                self._on_speak_state(False)


class MainWindow:
    """Окно приложения. Запускается из ``run_gui()``."""

    def __init__(
        self,
        config: Config,
        real_speaker: Any,
        recognizer: Any | None,
        llm: GeminiClient | None,
    ) -> None:
        self.config = config
        self.recognizer = recognizer
        self.llm = llm
        self._event_q: queue.Queue[tuple[str, str]] = queue.Queue()
        self._mic_enabled = recognizer is not None
        self._stt_thread: threading.Thread | None = None
        self._stt_stop = threading.Event()
        self._is_speaking = False

        self.root = tk.Tk()
        self.root.title("Jarvis · Голосовой ассистент")
        self.root.geometry("760x600")
        self.root.minsize(560, 420)
        self._build_ui()

        self._gui_speaker = _GuiSpeaker(
            real_speaker=real_speaker,
            on_text=lambda t: self._safe_after(("jarvis", t)),
            on_speak_state=self._on_speak_state,
        )
        # В GUI-режиме wake-word не обязателен — пользователь специально открыл окно.
        wake = WakeWordDetector(config.wake_words, always_active=True)
        self.assistant = Assistant(
            config=config,
            speaker=self._gui_speaker,
            wake_detector=wake,
            llm=llm,
            open_settings=self._schedule_open_settings,
        )

        # Приветствие.
        self.root.after(100, self._on_start)
        self.root.after(100, self._drain_events)
        if self._mic_enabled:
            self._start_stt()
        else:
            self._set_status(_STATUS_MIC_OFF)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ----- UI -------------------------------------------------------------

    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        with contextlib.suppress(Exception):
            style.theme_use("clam")

        outer = ttk.Frame(self.root, padding=8)
        outer.pack(fill="both", expand=True)

        # Header: статус слева, кнопки справа.
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 6))

        self._status_var = tk.StringVar(value=_STATUS_IDLE)
        ttk.Label(header, textvariable=self._status_var, font=("Segoe UI", 12, "bold")).pack(side="left")

        ttk.Button(header, text="Настройки", command=self._open_settings).pack(side="right", padx=2)
        ttk.Button(header, text="Очистить", command=self._clear_chat).pack(side="right", padx=2)
        self._mic_btn = ttk.Button(header, text="Микрофон: вкл", command=self._toggle_mic)
        self._mic_btn.pack(side="right", padx=2)
        if not self._mic_enabled:
            self._mic_btn.configure(text="Микрофон: нет", state="disabled")

        # Чат.
        self._chat = scrolledtext.ScrolledText(
            outer, wrap="word", state="disabled", font=("Segoe UI", 11), height=20
        )
        self._chat.pack(fill="both", expand=True)
        self._chat.tag_configure("user", foreground="#0a66c2", font=("Segoe UI", 11, "bold"))
        self._chat.tag_configure("jarvis", foreground="#107c10", font=("Segoe UI", 11, "bold"))
        self._chat.tag_configure("error", foreground="#a80000")
        self._chat.tag_configure("dim", foreground="#666666")

        # Ввод текста.
        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(6, 0))
        self._input_var = tk.StringVar()
        entry = ttk.Entry(bottom, textvariable=self._input_var, font=("Segoe UI", 11))
        entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        entry.bind("<Return>", lambda _e: self._on_send())
        entry.focus_set()
        ttk.Button(bottom, text="Отправить", command=self._on_send).pack(side="left")
        self._entry = entry

        # Подсказка.
        self._append_chat(
            "info",
            "Печатай команду внизу или просто говори в микрофон. "
            "Кнопка «Настройки» — изменить API-ключ и параметры.",
            tag="dim",
        )

    # ----- Events ---------------------------------------------------------

    def _safe_after(self, event: tuple[str, str]) -> None:
        """Можно безопасно вызывать из любого потока."""
        with contextlib.suppress(Exception):
            self._event_q.put_nowait(event)

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self._event_q.get_nowait()
                if kind == "user":
                    self._append_chat("Вы", payload, tag="user")
                elif kind == "jarvis":
                    self._append_chat("Джарвис", payload, tag="jarvis")
                elif kind == "status":
                    self._set_status(payload)
                elif kind == "error":
                    self._append_chat("Ошибка", payload, tag="error")
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)

    def _set_status(self, label: str) -> None:
        self._status_var.set(label)

    def _on_speak_state(self, speaking: bool) -> None:
        self._is_speaking = speaking
        self._safe_after(("status", _STATUS_SPEAK if speaking else self._idle_status()))

    def _idle_status(self) -> str:
        if not self._mic_enabled:
            return _STATUS_MIC_OFF
        return _STATUS_LISTEN

    def _append_chat(self, who: str, text: str, tag: str = "") -> None:
        self._chat.configure(state="normal")
        if tag:
            self._chat.insert("end", f"{who}: ", (tag,))
            self._chat.insert("end", text + "\n")
        else:
            self._chat.insert("end", f"{who}: {text}\n")
        self._chat.configure(state="disabled")
        self._chat.see("end")

    def _clear_chat(self) -> None:
        self._chat.configure(state="normal")
        self._chat.delete("1.0", "end")
        self._chat.configure(state="disabled")

    # ----- Actions --------------------------------------------------------

    def _on_start(self) -> None:
        try:
            self.assistant.greet()
        except Exception as exc:  # pragma: no cover
            self._safe_after(("error", f"Не удалось запустить ассистент: {exc}"))

    def _on_send(self) -> None:
        text = self._input_var.get().strip()
        if not text:
            return
        self._input_var.set("")
        self._safe_after(("user", text))
        threading.Thread(
            target=self._dispatch_command, args=(text,), daemon=True, name="jarvis-dispatch"
        ).start()

    def _toggle_mic(self) -> None:
        if not self._mic_enabled and self.recognizer is None:
            return
        self._mic_enabled = not self._mic_enabled
        if self._mic_enabled:
            self._mic_btn.configure(text="Микрофон: вкл")
            self._safe_after(("status", _STATUS_LISTEN))
            self._start_stt()
        else:
            self._mic_btn.configure(text="Микрофон: выкл")
            self._safe_after(("status", _STATUS_MIC_OFF))
            self._stt_stop.set()

    def _open_settings(self) -> None:
        self._schedule_open_settings("Изменение настроек Jarvis")

    def _schedule_open_settings(self, reason: str) -> None:
        """Безопасный вызов из любого потока — открывает окно в главном Tk-потоке."""

        def _go() -> None:
            try:
                from .settings import open_settings_dialog

                result = open_settings_dialog(reason=reason)
                if result is not None:
                    self._safe_after(
                        ("jarvis", "Настройки сохранены. Перезапустите Jarvis, чтобы применить.")
                    )
            except Exception as exc:  # pragma: no cover
                self._safe_after(("error", f"Не удалось открыть настройки: {exc}"))

        with contextlib.suppress(Exception):
            self.root.after(0, _go)

    def _on_close(self) -> None:
        self._stt_stop.set()
        with contextlib.suppress(Exception):
            self.root.destroy()

    # ----- Dispatch / STT -------------------------------------------------

    def _dispatch_command(self, text: str) -> None:
        """Один обработанный голос/текст. Запускается в worker-потоке.

        Делегирует роутинг (LLM-first vs локальный) в Assistant._handle(),
        чтобы логика была в одном месте. Перед уходом в Gemini проговаривает
        короткое подтверждение, чтобы пользователь слышал отклик сразу.
        """
        norm = text.strip().lower()
        if not norm:
            return
        if any(ex in norm for ex in EXIT_PHRASES):
            self._gui_speaker.speak("Завершаю работу. До связи, сэр.")
            self.root.after(1500, self._on_close)
            return

        self._safe_after(("status", _STATUS_THINK))

        # Голосовая «квитанция» — звучит, пока Gemini думает.
        agent_with_llm = (
            self.config.agent_mode and self.llm is not None and self.llm.available
        )
        if agent_with_llm:
            self._gui_speaker.speak(random.choice(_ACKS))

        try:
            self.assistant._handle(text)  # noqa: SLF001
        except Exception as exc:  # pragma: no cover
            log.error("dispatch failed: %s", exc)
            self._safe_after(("error", f"Ошибка: {exc}"))
        finally:
            self._safe_after(("status", self._idle_status()))

    def _start_stt(self) -> None:
        if not self.recognizer:
            return
        if self._stt_thread and self._stt_thread.is_alive():
            return
        self._stt_stop.clear()
        self._stt_thread = threading.Thread(
            target=self._stt_loop, daemon=True, name="jarvis-stt"
        )
        self._stt_thread.start()

    def _stt_loop(self) -> None:
        try:
            phrases: Iterator[str] = self.recognizer.listen()
            for phrase in phrases:
                if self._stt_stop.is_set():
                    break
                if not self._mic_enabled or self._is_speaking:
                    continue
                phrase = phrase.strip()
                if not phrase:
                    continue
                # Жест простоты — wake-word не обязателен. Если фраза начинается
                # с wake-слова, отрезаем его.
                command = self._strip_wake(phrase)
                if command is None:
                    continue
                if not command:
                    self._gui_speaker.speak(random.choice(GREETINGS))
                    continue
                self._safe_after(("user", phrase))
                self._dispatch_command(command)
        except Exception as exc:  # pragma: no cover
            self._safe_after(("error", f"Микрофон: {exc}"))

    def _strip_wake(self, phrase: str) -> str | None:
        text = phrase.lower()
        for wake in self.config.wake_words:
            if wake in text:
                _, _, tail = text.partition(wake)
                return tail.strip(" ,.!?:;-")
        # Wake-word не требуется в GUI — принимаем фразу как команду.
        return phrase

    # ----- Loop -----------------------------------------------------------

    def mainloop(self) -> None:
        self.root.mainloop()


def run_gui(
    config: Config,
    real_speaker: Any,
    recognizer: Any | None,
    llm: GeminiClient | None,
) -> int:
    """Запускает главное окно. Возвращает код выхода."""
    window = MainWindow(config=config, real_speaker=real_speaker, recognizer=recognizer, llm=llm)
    window.mainloop()
    return 0
