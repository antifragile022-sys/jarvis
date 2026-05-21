"""Настройка логирования."""
from __future__ import annotations

import logging
import os
import sys


def setup_logging(level: str | None = None) -> logging.Logger:
    """Создаёт корневой логгер с человекочитаемым форматом."""
    level_name = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    log_level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger("jarvis")
    if root.handlers:
        root.setLevel(log_level)
        return root

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root.addHandler(handler)
    root.setLevel(log_level)
    root.propagate = False
    return root


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"jarvis.{name}")
