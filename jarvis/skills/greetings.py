"""Приветствия, благодарности и базовые ответы."""
from __future__ import annotations

import random
import re

from ..router import Intent, compile_patterns

HELLO = ["Здравствуйте, сэр.", "Добрый день.", "Приветствую."]
THANKS = ["Всегда пожалуйста.", "Рад был помочь.", "Обращайтесь."]
WHO = [
    "Я — Джарвис, ваш персональный голосовой ассистент.",
    "Меня зовут Джарвис. Готов помочь.",
]


def _hello(_m, _t):
    return random.choice(HELLO)


def _thanks(_m, _t):
    return random.choice(THANKS)


def _who(_m, _t):
    return random.choice(WHO)


def intents() -> list[Intent]:
    return [
        Intent(
            name="hello",
            patterns=compile_patterns([
                r"\b(привет|здравствуй|здарова|здравствуйте|добрый день|доброе утро|добрый вечер)\b",
            ]),
            handler=_hello,
            priority=10,
        ),
        Intent(
            name="thanks",
            patterns=compile_patterns([
                r"\b(спасибо|благодарю|спс)\b",
            ]),
            handler=_thanks,
            priority=10,
        ),
        Intent(
            name="who_are_you",
            patterns=compile_patterns([
                r"\bкто ты\b",
                r"\bкак тебя зовут\b",
                r"\bпредставься\b",
            ]),
            handler=_who,
            priority=10,
        ),
    ]


# silence unused import warning for re module (used by other skills via this module)
_ = re
