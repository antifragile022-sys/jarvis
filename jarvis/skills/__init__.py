"""Набор стандартных навыков (skills) ассистента."""
from __future__ import annotations

from ..config import Config
from ..router import Router
from . import (
    apps,
    brightness,
    greetings,
    power,
    screenshot,
    search,
    settings_skill,
    system_info,
    time_date,
    volume,
    weather,
    web,
)


def build_default_router(config: Config) -> Router:
    router = Router()
    router.extend(settings_skill.intents())  # highest priority
    router.extend(greetings.intents())
    router.extend(time_date.intents())
    router.extend(apps.intents())
    router.extend(web.intents())
    router.extend(search.intents())
    router.extend(volume.intents())
    router.extend(brightness.intents())
    router.extend(screenshot.intents(config))
    router.extend(power.intents())
    router.extend(system_info.intents())
    router.extend(weather.intents(config))
    return router


__all__ = ["build_default_router"]
