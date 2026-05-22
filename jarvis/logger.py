"""Настройка логирования."""
from __future__ import annotations

import contextlib
import logging
import logging.handlers
import os
import sys
from pathlib import Path


def _log_file_path() -> Path:
    from .settings_store import get_settings_dir

    return get_settings_dir() / "jarvis.log"


def setup_logging(level: str | None = None) -> logging.Logger:
    """Корневой логгер: stderr (если есть консоль) + ротация в файл."""
    level_name = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    log_level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger("jarvis")
    if root.handlers:
        root.setLevel(log_level)
        return root

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Файл — всегда (для windowed .exe без консоли).
    try:
        log_path = _log_file_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=1_000_000, backupCount=2, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except Exception:  # pragma: no cover
        pass

    # Stderr — только если есть рабочий поток (в windowed exe sys.stderr может быть None).
    with contextlib.suppress(Exception):
        if sys.stderr is not None and hasattr(sys.stderr, "write"):
            stream_handler = logging.StreamHandler(sys.stderr)
            stream_handler.setFormatter(fmt)
            root.addHandler(stream_handler)

    root.setLevel(log_level)
    root.propagate = False
    return root


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"jarvis.{name}")
