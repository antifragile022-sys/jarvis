"""Тесты конфигурации.

Конфигурация читается так: 1) %APPDATA%/Jarvis/config.json (settings_store),
2) переменные окружения (только если в settings пусто).
"""
from __future__ import annotations

import pytest

from jarvis import settings_store
from jarvis.config import load_config


@pytest.fixture(autouse=True)
def isolate_settings(tmp_path, monkeypatch):
    """Подменяем путь к config.json на временный, чтобы тесты не цепляли реальный файл."""
    fake_path = tmp_path / "config.json"
    monkeypatch.setattr(settings_store, "get_settings_path", lambda: fake_path)
    monkeypatch.setattr(settings_store, "get_settings_dir", lambda: tmp_path)
    yield


def test_defaults_when_no_file_and_no_env(monkeypatch):
    for k in (
        "GEMINI_API_KEY", "GEMINI_MODEL", "VOSK_MODEL_PATH",
        "WAKE_WORDS", "TTS_RATE", "DEFAULT_CITY", "MIC_DEVICE",
    ):
        monkeypatch.delenv(k, raising=False)
    c = load_config(env_file=None)
    assert c.gemini_model == "gemini-2.5-flash-lite"
    assert c.fallback_model == "gemini-2.5-flash"
    assert c.default_city == "Москва"
    assert "джарвис" in c.wake_words
    assert c.tts_rate == 180
    assert c.mic_device is None
    assert c.agent_mode is True
    assert c.auto_approve is False


def test_settings_store_takes_precedence_over_env(monkeypatch):
    # В env — одно, в файле — другое; должно победить значение из файла.
    monkeypatch.setenv("GEMINI_API_KEY", "from-env")
    settings_store.save_settings({
        **settings_store.DEFAULTS,
        "gemini_api_key": "from-file",
        "default_city": "Питер",
        "agent_mode": False,
    })
    c = load_config(env_file=None)
    assert c.gemini_api_key == "from-file"
    assert c.default_city == "Питер"
    assert c.agent_mode is False


def test_env_used_when_settings_file_empty(monkeypatch):
    # Файл не сохранён → берём из env.
    monkeypatch.setenv("GEMINI_API_KEY", "from-env")
    c = load_config(env_file=None)
    assert c.gemini_api_key == "from-env"


def test_is_first_run_true_when_no_file_and_no_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert settings_store.is_first_run() is True


def test_is_first_run_false_after_save():
    settings_store.save_settings({**settings_store.DEFAULTS, "gemini_api_key": "x"})
    assert settings_store.is_first_run() is False
