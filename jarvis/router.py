"""Маршрутизация распознанных фраз к навыкам (skills) на основе regex-паттернов."""
from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass


@dataclass
class Intent:
    name: str
    patterns: tuple[re.Pattern[str], ...]
    handler: Callable[[re.Match[str], str], str]
    priority: int = 0  # выше = матчится раньше


def compile_patterns(patterns: Iterable[str]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p, re.IGNORECASE) for p in patterns)


class Router:
    """Простой роутер: первый матч (по приоритету) выигрывает.

    Если ни один интент не подошёл, возвращается None — вызывающий код может
    переадресовать запрос в LLM.
    """

    def __init__(self) -> None:
        self._intents: list[Intent] = []

    def register(self, intent: Intent) -> None:
        self._intents.append(intent)
        self._intents.sort(key=lambda it: -it.priority)

    def extend(self, intents: Iterable[Intent]) -> None:
        for it in intents:
            self.register(it)

    @property
    def intents(self) -> list[Intent]:
        return list(self._intents)

    def match(self, phrase: str) -> tuple[Intent, re.Match[str]] | None:
        text = (phrase or "").lower().strip()
        if not text:
            return None
        for intent in self._intents:
            for pattern in intent.patterns:
                m = pattern.search(text)
                if m:
                    return intent, m
        return None

    def dispatch(self, phrase: str) -> str | None:
        """Возвращает ответ навыка или None, если фраза никуда не подошла."""
        matched = self.match(phrase)
        if not matched:
            return None
        intent, m = matched
        try:
            return intent.handler(m, phrase)
        except Exception as exc:  # noqa: BLE001
            return f"Не получилось выполнить «{intent.name}»: {exc}"
