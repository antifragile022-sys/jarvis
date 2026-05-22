"""Точка входа для PyInstaller — оборачивает пакет `jarvis` в одиночный .exe.

Запускать обычно следует `python -m jarvis ...`. Этот файл нужен, чтобы
PyInstaller мог собрать пакет (с относительными импортами) в один бинарь.
"""
from __future__ import annotations

import contextlib
import io
import sys


def _force_utf8_stdio() -> None:
    """В Windows-консоли по умолчанию cp1252 → кириллица в print падает."""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        enc = (getattr(stream, "encoding", "") or "").lower()
        if enc == "utf-8":
            continue
        reconfigured = False
        with contextlib.suppress(Exception):
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
            reconfigured = True
        if reconfigured:
            continue
        with contextlib.suppress(Exception):
            setattr(sys, name, io.TextIOWrapper(stream.buffer, encoding="utf-8", line_buffering=True))


_force_utf8_stdio()

from jarvis.__main__ import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
