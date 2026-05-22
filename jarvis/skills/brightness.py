"""Управление яркостью экрана."""
from __future__ import annotations

from ..logger import get_logger
from ..router import Intent, compile_patterns

log = get_logger("skills.brightness")


def _set_brightness(pct: int) -> bool:
    try:
        import screen_brightness_control as sbc  # type: ignore
    except ImportError:
        return False
    try:
        sbc.set_brightness(max(0, min(pct, 100)))
        return True
    except Exception as exc:  # pragma: no cover
        log.error("brightness set failed: %s", exc)
        return False


def _get_brightness() -> int | None:
    try:
        import screen_brightness_control as sbc  # type: ignore
    except ImportError:
        return None
    try:
        vals = sbc.get_brightness()
        if isinstance(vals, list) and vals:
            return int(vals[0])
        if isinstance(vals, int):
            return vals
    except Exception:
        pass
    return None


def _handle_set(m, _t):
    val = int(m.group("pct"))
    if _set_brightness(val):
        return f"Яркость {val} процентов."
    return "Не удалось изменить яркость."


def _handle_up(_m, _t):
    cur = _get_brightness() or 50
    new = min(cur + 15, 100)
    if _set_brightness(new):
        return f"Ярче. Сейчас {new} процентов."
    return "Не удалось изменить яркость."


def _handle_down(_m, _t):
    cur = _get_brightness() or 50
    new = max(cur - 15, 0)
    if _set_brightness(new):
        return f"Темнее. Сейчас {new} процентов."
    return "Не удалось изменить яркость."


def intents() -> list[Intent]:
    return [
        Intent(
            name="brightness_set",
            patterns=compile_patterns([
                r"\bяркость\s+(?:на\s+)?(?P<pct>\d{1,3})\b",
                r"\bпоставь\s+яркость\s+(?:на\s+)?(?P<pct>\d{1,3})\b",
                r"\bсделай\s+яркость\s+(?P<pct>\d{1,3})\b",
            ]),
            handler=_handle_set,
            priority=30,
        ),
        Intent(
            name="brightness_up",
            patterns=compile_patterns([
                r"\b(?:сделай\s+)?ярче\b",
                r"\bувеличь\s+яркость\b",
            ]),
            handler=_handle_up,
            priority=25,
        ),
        Intent(
            name="brightness_down",
            patterns=compile_patterns([
                r"\b(?:сделай\s+)?темнее\b",
                r"\bуменьши\s+яркость\b",
            ]),
            handler=_handle_down,
            priority=25,
        ),
    ]
