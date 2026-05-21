"""Speech-to-Text через Vosk (оффлайн, русский язык)."""
from __future__ import annotations

import json
import queue
import sys
from collections.abc import Iterator
from pathlib import Path

from .logger import get_logger

log = get_logger("stt")

SAMPLE_RATE = 16000
BLOCK_SIZE = 8000


def _resolve_model_path(raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute() and p.exists():
        return p

    candidates: list[Path] = []
    if p.exists():
        candidates.append(p.resolve())

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / raw)

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / raw)
        candidates.append(exe_dir / Path(raw).name)

    for c in candidates:
        if c.exists():
            return c
    return p


class VoskRecognizer:
    """Поток распознавания: слушает микрофон и возвращает финализированные фразы."""

    def __init__(self, model_path: str, device: int | None = None) -> None:
        self._model_path = _resolve_model_path(model_path)
        self._device = device
        self._queue: queue.Queue[bytes] = queue.Queue()
        self._model = None
        self._rec = None
        self._sd = None

    def _ensure_loaded(self) -> None:
        if self._rec is not None:
            return

        if not self._model_path.exists():
            raise FileNotFoundError(
                f"Vosk-модель не найдена: {self._model_path}. "
                "Скачай с https://alphacephei.com/vosk/models и распакуй, "
                "путь к ней пропиши в настройках."
            )

        try:
            from vosk import KaldiRecognizer, Model, SetLogLevel  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Пакет `vosk` не установлен.") from exc

        try:
            import sounddevice as sd  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Пакет `sounddevice` не установлен.") from exc

        SetLogLevel(-1)
        log.info("Загружаю Vosk-модель: %s", self._model_path)
        self._model = Model(str(self._model_path))
        self._rec = KaldiRecognizer(self._model, SAMPLE_RATE)
        self._rec.SetWords(False)
        self._sd = sd

    def listen(self) -> Iterator[str]:
        self._ensure_loaded()
        assert self._rec is not None and self._sd is not None

        def _callback(indata, _frames, _time, status):
            if status:
                log.debug("sounddevice status: %s", status)
            self._queue.put(bytes(indata))

        log.info("Слушаю микрофон…")
        with self._sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            dtype="int16",
            channels=1,
            device=self._device,
            callback=_callback,
        ):
            while True:
                data = self._queue.get()
                if self._rec.AcceptWaveform(data):
                    payload = json.loads(self._rec.Result() or "{}")
                    text = (payload.get("text") or "").strip()
                    if text:
                        log.info("← %s", text)
                        yield text


def text_input_iter(prompt: str = "Ты: ") -> Iterator[str]:
    """Заменитель распознавания для текстового режима — читает строки из stdin."""
    while True:
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            return
        line = line.strip()
        if line:
            yield line
