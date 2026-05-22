"""Детектор wake-word на основе строкового сравнения распознанного текста."""
from __future__ import annotations

import re
from collections.abc import Iterable


class WakeWordDetector:
    """Возвращает «полезную часть» команды, если фраза начинается с wake-word.

    Поведение:
      - если в фразе есть wake-word, отрезает его и возвращает оставшийся текст;
      - если после wake-word ничего нет — возвращает пустую строку (значит,
        активация прошла, но команды нет — ассистент должен переспросить);
      - если wake-word не найден — возвращает None.
    """

    def __init__(self, wake_words: Iterable[str], always_active: bool = False) -> None:
        cleaned = [w.strip().lower() for w in wake_words if w and w.strip()]
        cleaned.sort(key=len, reverse=True)  # длинные сначала, чтобы матчить «эй джарвис» раньше «джарвис»
        self._wake_words = tuple(cleaned)
        self._always_active = always_active

    @property
    def always_active(self) -> bool:
        return self._always_active

    def detect(self, phrase: str) -> str | None:
        text = (phrase or "").lower().strip()
        if not text:
            return None

        if self._always_active:
            return text

        for ww in self._wake_words:
            if ww in text:
                # Берём всё после wake-word и чистим от пунктуации/частиц.
                idx = text.find(ww)
                rest = text[idx + len(ww):]
                rest = re.sub(r"^[\s,.!?:;\-]+", "", rest)
                rest = re.sub(r"^(пожалуйста|плиз|please)\s+", "", rest)
                return rest.strip()
        return None
