"""Голосовой поиск как универсальная команда «найди X» → Google."""
from __future__ import annotations

import urllib.parse
import webbrowser

from ..router import Intent, compile_patterns


def _search(m, _t):
    query = (m.group("q") or "").strip()
    if not query:
        return "Что найти?"
    url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
    webbrowser.open(url, new=2)
    return f"Ищу: {query}."


def intents() -> list[Intent]:
    # Низкий приоритет — чтобы более специфичные интенты («открой ютуб», «загугли X»)
    # сработали раньше.
    return [
        Intent(
            name="generic_search",
            patterns=compile_patterns([
                r"\b(?:найди|поищи|поиск)\s+(?P<q>.+?)\s*$",
            ]),
            handler=_search,
            priority=1,
        ),
    ]
