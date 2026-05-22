"""Text-to-Speech через pyttsx3 (SAPI5 на Windows, NSSpeechSynthesizer на macOS, espeak на Linux)."""
from __future__ import annotations

import contextlib
from threading import Lock

from .logger import get_logger

log = get_logger("tts")


class Speaker:
    """Тонкая обёртка над pyttsx3 с потокобезопасным speak()."""

    def __init__(self, voice: str = "", rate: int = 180, volume: float = 1.0) -> None:
        self._lock = Lock()
        self._engine = None
        self._voice_hint = voice
        self._rate = rate
        self._volume = max(0.0, min(volume, 1.0))
        self._init_engine()

    def _init_engine(self) -> None:
        try:
            import pyttsx3
        except ImportError as exc:  # pragma: no cover
            log.error("pyttsx3 не установлен: %s", exc)
            self._engine = None
            return

        try:
            engine = pyttsx3.init()
        except Exception as exc:  # pragma: no cover - зависит от платформы
            log.error("Не удалось инициализировать pyttsx3: %s", exc)
            self._engine = None
            return

        engine.setProperty("rate", self._rate)
        engine.setProperty("volume", self._volume)

        chosen = self._select_voice(engine)
        if chosen is not None:
            engine.setProperty("voice", chosen)

        self._engine = engine

    def _select_voice(self, engine) -> str | None:
        try:
            voices = engine.getProperty("voices") or []
        except Exception:  # pragma: no cover
            return None

        hint = (self._voice_hint or "").lower().strip()

        if hint:
            for v in voices:
                if hint in (v.id or "").lower() or hint in (v.name or "").lower():
                    log.info("TTS voice (по hint=%r): %s", hint, v.name)
                    return v.id

        # Без подсказки — берём первый русский голос, если есть.
        for v in voices:
            langs: list[str] = []
            with contextlib.suppress(Exception):
                langs = [str(lang).lower() for lang in (v.languages or [])]
            text = " ".join([str(v.id or ""), str(v.name or ""), *langs]).lower()
            if "ru" in text or "russian" in text or "русс" in text:
                log.info("TTS voice (RU auto): %s", v.name)
                return v.id

        if voices:
            log.warning("Русский голос не найден, использую %s", voices[0].name)
            return voices[0].id

        return None

    def list_voices(self) -> list[dict[str, str]]:
        if not self._engine:
            return []
        try:
            voices = self._engine.getProperty("voices") or []
        except Exception:
            return []
        return [
            {
                "id": v.id or "",
                "name": v.name or "",
                "languages": ",".join(str(x) for x in (v.languages or [])),
            }
            for v in voices
        ]

    def speak(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        log.info("→ %s", text)
        if not self._engine:
            return
        with self._lock:
            try:
                self._engine.say(text)
                self._engine.runAndWait()
            except RuntimeError:
                # Бывает, если предыдущий runAndWait не завершился — переинициализация.
                self._init_engine()
                if self._engine:
                    self._engine.say(text)
                    self._engine.runAndWait()
            except Exception as exc:  # pragma: no cover
                log.error("Ошибка TTS: %s", exc)


class PrintSpeaker:
    """Заглушка-«говорилка» для текстового режима — просто печатает в stdout."""

    def speak(self, text: str) -> None:
        print(f"[JARVIS] {text}")

    def list_voices(self) -> list[dict[str, str]]:
        return []
