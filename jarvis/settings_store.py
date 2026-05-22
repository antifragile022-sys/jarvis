"""Хранилище настроек пользователя в %APPDATA%/Jarvis/config.json.

Эти настройки **перекрывают** значения из .env / переменных окружения.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from .logger import get_logger

log = get_logger("settings_store")


def get_settings_dir() -> Path:
    """Папка для хранения пользовательских настроек."""
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "Jarvis"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Jarvis"
    xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(xdg) / "jarvis"


def get_settings_path() -> Path:
    return get_settings_dir() / "config.json"


DEFAULTS: dict[str, Any] = {
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash-lite",
    "fallback_model": "gemini-2.5-flash",
    "wake_words": ["джарвис", "jarvis", "эй джарвис"],
    "tts_voice": "",
    "tts_rate": 180,
    "tts_volume": 1.0,
    "vosk_model_path": "models/vosk-model-small-ru-0.22",
    "mic_device": None,
    "default_city": "Москва",
    "agent_mode": True,
    "auto_approve": False,
    "screenshots_dir": "",
    "log_level": "INFO",
}


def load_settings() -> dict[str, Any]:
    """Читает config.json. Если файла нет — возвращает копию DEFAULTS."""
    path = get_settings_path()
    if not path.exists():
        return DEFAULTS.copy()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Не смог прочитать %s: %s. Беру значения по умолчанию.", path, exc)
        return DEFAULTS.copy()
    merged = DEFAULTS.copy()
    for k, v in data.items():
        if k in DEFAULTS:
            merged[k] = v
    return merged


def save_settings(values: dict[str, Any]) -> None:
    path = get_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Сохраняем только известные ключи, чтобы не плодить мусор.
    payload = {k: values.get(k, DEFAULTS[k]) for k in DEFAULTS}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Настройки сохранены: %s", path)


def update_setting(key: str, value: Any) -> dict[str, Any]:
    cur = load_settings()
    cur[key] = value
    save_settings(cur)
    return cur


def is_first_run() -> bool:
    """True, если файла настроек ещё нет ИЛИ нет ключа Gemini."""
    s = load_settings()
    return not get_settings_path().exists() or not (s.get("gemini_api_key") or "").strip()
