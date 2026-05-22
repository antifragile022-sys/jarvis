"""Локальный навык: открыть окно настроек / сменить ключ."""
from __future__ import annotations

import threading

from ..router import Intent, compile_patterns


def _open_settings(_m, _t):
    # Импорт внутри — Tk может быть не нужен в текстовом режиме.
    from ..gui.settings import open_settings_dialog

    # В отдельный поток — чтобы не блокировать STT-цикл.
    threading.Thread(
        target=open_settings_dialog,
        kwargs={"reason": ""},
        daemon=True,
    ).start()
    return "Открываю настройки."


def intents() -> list[Intent]:
    return [
        Intent(
            name="open_settings",
            patterns=compile_patterns([
                r"\bоткрой(?:\s+(?:окно|меню))?\s+настройки\b",
                r"\bпокажи\s+настройки\b",
                r"\bнастройки\s+(?:открой|покажи)\b",
                r"\bсмени(?:ть)?\s+(?:api[- ]?)?ключ\b",
                r"\bизмени(?:ть)?\s+(?:api[- ]?)?ключ\b",
                r"\bобнови(?:ть)?\s+ключ\b",
            ]),
            handler=_open_settings,
            priority=50,
        ),
    ]
