"""Время и дата."""
from __future__ import annotations

from datetime import datetime

from ..router import Intent, compile_patterns

MONTHS_RU = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]
WEEKDAYS_RU = [
    "понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье",
]


def _say_time(_m, _t):
    now = datetime.now()
    return f"Сейчас {now.hour} часов {now.minute:02d} минут."


def _say_date(_m, _t):
    now = datetime.now()
    return (
        f"Сегодня {now.day} {MONTHS_RU[now.month - 1]} {now.year} года, "
        f"{WEEKDAYS_RU[now.weekday()]}."
    )


def _say_weekday(_m, _t):
    return f"Сегодня {WEEKDAYS_RU[datetime.now().weekday()]}."


def intents() -> list[Intent]:
    return [
        Intent(
            name="time",
            patterns=compile_patterns([
                r"\b(сколько (сейчас )?времени|который час|время сейчас|текущее время)\b",
            ]),
            handler=_say_time,
            priority=20,
        ),
        Intent(
            name="date",
            patterns=compile_patterns([
                r"\b(какая (сегодня )?дата|какое (сегодня )?число|сегодняшняя дата)\b",
            ]),
            handler=_say_date,
            priority=20,
        ),
        Intent(
            name="weekday",
            patterns=compile_patterns([
                r"\bкакой (сегодня )?день недели\b",
                r"\bкакой сегодня день\b",
            ]),
            handler=_say_weekday,
            priority=20,
        ),
    ]
