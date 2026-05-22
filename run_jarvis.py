"""Точка входа для PyInstaller — оборачивает пакет `jarvis` в одиночный .exe.

Запускать обычно следует `python -m jarvis ...`. Этот файл нужен, чтобы
PyInstaller мог собрать пакет (с относительными импортами) в один бинарь.
"""
from __future__ import annotations

import contextlib
import io
import sys
import traceback


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


def _show_error_dialog(message: str) -> None:
    """Показывает Tk-окошко с ошибкой (для windowed .exe — иначе ошибка пропадает)."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showerror("Jarvis · Ошибка", message)
        with contextlib.suppress(Exception):
            root.destroy()
    except Exception:
        pass


_force_utf8_stdio()


def _excepthook(exc_type, exc_value, exc_tb):
    text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    # Попробуем дописать в лог-файл (если уже сконфигурирован).
    with contextlib.suppress(Exception):
        from jarvis.logger import setup_logging  # late import

        setup_logging().error("Неперехваченная ошибка:\n%s", text)
    _show_error_dialog(
        "Что-то пошло не так. Подробности — в %APPDATA%\\Jarvis\\jarvis.log\n\n"
        + text[-1500:]
    )
    sys.exit(1)


sys.excepthook = _excepthook


from jarvis.__main__ import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
