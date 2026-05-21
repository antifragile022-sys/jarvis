"""Загрузка конфигурации: сначала settings_store, потом .env / env-vars как fallback."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):  # type: ignore[no-redef]
        return False

from .settings_store import load_settings


@dataclass(frozen=True)
class Config:
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"
    fallback_model: str = "gemini-2.5-flash"

    vosk_model_path: str = "models/vosk-model-small-ru-0.22"

    wake_words: tuple[str, ...] = ("джарвис", "jarvis", "эй джарвис")

    tts_voice: str = ""
    tts_rate: int = 180
    tts_volume: float = 1.0

    default_city: str = "Москва"

    mic_device: int | None = None

    agent_mode: bool = True
    auto_approve: bool = False

    screenshots_dir: Path = field(default_factory=lambda: Path.home() / "Pictures" / "Jarvis")
    log_level: str = "INFO"


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip().lower() for part in value.split(",") if part.strip())


def _parse_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_optional_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on", "да")


def load_config(env_file: str | os.PathLike[str] | None = ".env") -> Config:
    """Слой 1 — settings_store (config.json), слой 2 — .env / env-vars (для совместимости)."""
    if env_file:
        load_dotenv(env_file, override=False)

    s = load_settings()

    # Если в config.json ключ пустой — пробуем взять из env (для разработчиков).
    api_key = (s.get("gemini_api_key") or "").strip() or os.getenv("GEMINI_API_KEY", "").strip()

    wake = s.get("wake_words") or []
    if isinstance(wake, str):
        wake_tuple = _split_csv(wake)
    else:
        wake_tuple = tuple(w.lower().strip() for w in wake if w and w.strip())
    if not wake_tuple:
        wake_tuple = _split_csv(os.getenv("WAKE_WORDS", "джарвис,jarvis,эй джарвис"))

    screenshots_raw = (s.get("screenshots_dir") or os.getenv("SCREENSHOTS_DIR", "")).strip()
    screenshots_dir = Path(screenshots_raw) if screenshots_raw else (Path.home() / "Pictures" / "Jarvis")

    return Config(
        gemini_api_key=api_key,
        gemini_model=(s.get("gemini_model") or os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")).strip(),
        fallback_model=(s.get("fallback_model") or "gemini-2.5-flash").strip(),
        vosk_model_path=(s.get("vosk_model_path") or os.getenv("VOSK_MODEL_PATH", "models/vosk-model-small-ru-0.22")).strip(),
        wake_words=wake_tuple,
        tts_voice=(s.get("tts_voice") or os.getenv("TTS_VOICE", "")).strip(),
        tts_rate=_parse_int(s.get("tts_rate") or os.getenv("TTS_RATE"), 180),
        tts_volume=_parse_float(s.get("tts_volume") or os.getenv("TTS_VOLUME"), 1.0),
        default_city=(s.get("default_city") or os.getenv("DEFAULT_CITY", "Москва")).strip() or "Москва",
        mic_device=_parse_optional_int(s.get("mic_device") if s.get("mic_device") not in (None, "") else os.getenv("MIC_DEVICE")),
        agent_mode=_parse_bool(s.get("agent_mode"), True),
        auto_approve=_parse_bool(s.get("auto_approve"), False),
        screenshots_dir=screenshots_dir,
        log_level=(s.get("log_level") or os.getenv("LOG_LEVEL", "INFO")).strip().upper() or "INFO",
    )
