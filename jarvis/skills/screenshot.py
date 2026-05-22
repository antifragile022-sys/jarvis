"""Скриншоты."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..config import Config
from ..logger import get_logger
from ..router import Intent, compile_patterns

log = get_logger("skills.screenshot")


def _make_handler(config: Config):
    def _take(_m, _t):
        try:
            import pyautogui  # type: ignore
        except ImportError:
            return "Установи pyautogui, чтобы делать скриншоты."

        directory = Path(config.screenshots_dir)
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
        path = directory / filename
        try:
            img = pyautogui.screenshot()
            img.save(str(path))
        except Exception as exc:  # pragma: no cover
            log.error("screenshot failed: %s", exc)
            return f"Не удалось сохранить скриншот: {exc}"
        return f"Скриншот сохранён в {path}."

    return _take


def intents(config: Config) -> list[Intent]:
    return [
        Intent(
            name="screenshot",
            patterns=compile_patterns([
                r"\b(?:сделай\s+)?(?:скриншот|снимок\s+экрана|скрин)\b",
                r"\bсфоткай\s+экран\b",
            ]),
            handler=_make_handler(config),
            priority=20,
        ),
    ]
