"""Точка входа CLI:
  python -m jarvis              # голосовой режим (по умолчанию)
  python -m jarvis voice        # то же самое
  python -m jarvis text         # текстовый режим (без микрофона)
  python -m jarvis once "X"     # выполнить одну команду и выйти
  python -m jarvis settings     # открыть окно настроек
  python -m jarvis voices       # список TTS-голосов
  python -m jarvis devices      # список аудио-устройств
"""
from __future__ import annotations

import argparse
import io
import sys
from collections.abc import Iterator

# Принуждаем UTF-8 в консоли Windows, иначе кириллица в print падает (cp1252).
if sys.stdout and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)
        except Exception:
            pass

from . import agent_tools
from .assistant import Assistant
from .config import load_config
from .llm import GeminiClient
from .logger import get_logger, setup_logging
from .settings_store import is_first_run
from .stt import VoskRecognizer, text_input_iter
from .tts import PrintSpeaker, Speaker
from .wakeword import WakeWordDetector


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="jarvis", description="Голосовой ассистент Джарвис")
    sub = parser.add_subparsers(dest="cmd")

    p_voice = sub.add_parser("voice", help="Голосовой режим (по умолчанию)")
    p_voice.add_argument("--no-wake", action="store_true", help="Не требовать wake-word.")

    p_text = sub.add_parser("text", help="Текстовый режим — ввод с клавиатуры")
    p_text.add_argument("--with-wake", action="store_true", help="Требовать wake-word.")

    p_once = sub.add_parser("once", help="Выполнить одну команду и выйти")
    p_once.add_argument("text", nargs="+")

    sub.add_parser("settings", help="Открыть окно настроек")
    sub.add_parser("voices", help="Показать TTS-голоса")
    sub.add_parser("devices", help="Показать аудио-устройства")

    return parser.parse_args(argv)


def _build_llm(config) -> GeminiClient | None:
    if not config.gemini_api_key:
        return None
    tools = agent_tools.ALL_TOOLS if config.agent_mode else None
    agent_tools.configure(auto_approve=config.auto_approve, screenshots_dir=config.screenshots_dir)
    return GeminiClient(
        api_key=config.gemini_api_key,
        model=config.gemini_model,
        fallback_model=config.fallback_model,
        tools=tools,
    )


def _ensure_first_run_setup() -> None:
    """Если первая загрузка — показываем окно настроек до запуска."""
    if not is_first_run():
        return
    try:
        from .gui.settings import open_settings_dialog
        open_settings_dialog(
            reason="Первый запуск: введи API-ключ Gemini (бесплатно: https://aistudio.google.com/app/apikey)"
        )
    except Exception as exc:
        print(f"[Jarvis] Не удалось показать окно настроек: {exc}", file=sys.stderr)


def _run_voice(args: argparse.Namespace) -> int:
    _ensure_first_run_setup()
    config = load_config()
    setup_logging(config.log_level)
    log = get_logger("main")

    try:
        recognizer = VoskRecognizer(config.vosk_model_path, device=config.mic_device)
        recognizer._ensure_loaded()  # noqa: SLF001
    except Exception as exc:
        log.error("STT init failed: %s", exc)
        print(f"[Jarvis] {exc}", file=sys.stderr)
        return 2

    speaker = Speaker(voice=config.tts_voice, rate=config.tts_rate, volume=config.tts_volume)
    wake = WakeWordDetector(config.wake_words, always_active=getattr(args, "no_wake", False))
    llm = _build_llm(config)
    assistant = Assistant(config=config, speaker=speaker, wake_detector=wake, llm=llm)

    assistant.greet()
    try:
        assistant.run(recognizer.listen())
    except KeyboardInterrupt:
        speaker.speak("Завершаю работу.")
    return 0


def _run_text(args: argparse.Namespace) -> int:
    config = load_config()
    setup_logging(config.log_level)

    speaker = PrintSpeaker()
    wake = WakeWordDetector(config.wake_words, always_active=not getattr(args, "with_wake", False))
    llm = _build_llm(config)
    assistant = Assistant(config=config, speaker=speaker, wake_detector=wake, llm=llm)

    print("[Jarvis] Текстовый режим. Пиши команду и Enter. Ctrl+C — выход.")
    assistant.greet()
    try:
        assistant.run(text_input_iter())
    except KeyboardInterrupt:
        print("\n[Jarvis] До связи.")
    return 0


def _run_once(args: argparse.Namespace) -> int:
    config = load_config()
    setup_logging(config.log_level)
    phrase = " ".join(args.text)

    speaker = PrintSpeaker()
    wake = WakeWordDetector(config.wake_words, always_active=True)
    llm = _build_llm(config)
    assistant = Assistant(config=config, speaker=speaker, wake_detector=wake, llm=llm)

    def _one() -> Iterator[str]:
        yield phrase

    assistant.run(_one())
    return 0


def _open_settings() -> int:
    try:
        from .gui.settings import open_settings_dialog
        open_settings_dialog()
        return 0
    except Exception as exc:
        print(f"[Jarvis] Не удалось открыть настройки: {exc}", file=sys.stderr)
        return 1


def _list_voices() -> int:
    speaker = Speaker()
    for v in speaker.list_voices():
        print(f"- id={v['id']}\n  name={v['name']}\n  langs={v['languages']}")
    return 0


def _list_devices() -> int:
    try:
        import sounddevice as sd  # type: ignore
    except ImportError:
        print("sounddevice не установлен.", file=sys.stderr)
        return 1
    for i, dev in enumerate(sd.query_devices()):
        kind = []
        if dev.get("max_input_channels"):
            kind.append("вход")
        if dev.get("max_output_channels"):
            kind.append("выход")
        print(f"{i:>3}: {dev.get('name')} [{', '.join(kind)}]")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    cmd = args.cmd or "voice"
    if cmd == "settings":
        return _open_settings()
    if cmd == "voices":
        return _list_voices()
    if cmd == "devices":
        return _list_devices()
    if cmd == "text":
        return _run_text(args)
    if cmd == "once":
        return _run_once(args)
    return _run_voice(args)


if __name__ == "__main__":
    raise SystemExit(main())
