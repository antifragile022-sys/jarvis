"""Открытие сайтов и поиск в интернете."""
from __future__ import annotations

import urllib.parse
import webbrowser

from ..router import Intent, compile_patterns

SITES: dict[str, str] = {
    "ютуб": "https://www.youtube.com/",
    "youtube": "https://www.youtube.com/",
    "гугл": "https://www.google.com/",
    "google": "https://www.google.com/",
    "яндекс": "https://ya.ru/",
    "yandex": "https://ya.ru/",
    "гитхаб": "https://github.com/",
    "github": "https://github.com/",
    "телеграм веб": "https://web.telegram.org/",
    "вики": "https://ru.wikipedia.org/",
    "википедия": "https://ru.wikipedia.org/",
    "вконтакте": "https://vk.com/",
    "вк": "https://vk.com/",
    "почта": "https://mail.google.com/",
    "гмейл": "https://mail.google.com/",
    "карты": "https://yandex.ru/maps/",
    "погода": "https://yandex.ru/pogoda/",
    "хабр": "https://habr.com/",
    "twitch": "https://www.twitch.tv/",
    "твич": "https://www.twitch.tv/",
}


def _open_site(m, _t):
    name = (m.group("site") or "").strip().lower()
    if not name:
        return "Какой сайт открыть?"
    url = SITES.get(name)
    if not url:
        # Если выглядит как домен — открываем напрямую.
        if "." in name and " " not in name:
            url = name if name.startswith("http") else f"https://{name}"
        else:
            return f"Не знаю сайт «{name}»."
    webbrowser.open(url, new=2)
    return f"Открываю {name}."


def _google(m, _t):
    query = (m.group("q") or "").strip()
    if not query:
        return "Что найти в Гугле?"
    url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
    webbrowser.open(url, new=2)
    return f"Ищу в Гугле: {query}."


def _youtube(m, _t):
    query = (m.group("q") or "").strip()
    if not query:
        return "Что найти на Ютубе?"
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
    webbrowser.open(url, new=2)
    return f"Ищу на Ютубе: {query}."


def intents() -> list[Intent]:
    return [
        Intent(
            name="open_site",
            patterns=compile_patterns([
                r"\bоткрой(?:\s+сайт)?\s+(?P<site>[\w\s\.\-]+?)\s*$",
                r"\bперейди на\s+(?P<site>[\w\s\.\-]+?)\s*$",
            ]),
            handler=_open_site,
            priority=15,
        ),
        Intent(
            name="google_search",
            patterns=compile_patterns([
                r"\b(?:загугли|поищи в гугле|найди в гугле|погугли)\s+(?P<q>.+?)\s*$",
            ]),
            handler=_google,
            priority=20,
        ),
        Intent(
            name="youtube_search",
            patterns=compile_patterns([
                r"\b(?:найди на ютубе|поищи на ютубе|включи на ютубе)\s+(?P<q>.+?)\s*$",
            ]),
            handler=_youtube,
            priority=20,
        ),
    ]
