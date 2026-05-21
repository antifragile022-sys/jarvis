"""Информация о системе: CPU, RAM, диск, батарея."""
from __future__ import annotations

import contextlib

from ..router import Intent, compile_patterns


def _say_cpu(_m, _t):
    try:
        import psutil  # type: ignore
    except ImportError:
        return "Установи psutil, чтобы узнавать загрузку процессора."
    pct = psutil.cpu_percent(interval=0.5)
    return f"Загрузка процессора {pct:.0f} процентов."


def _say_ram(_m, _t):
    try:
        import psutil  # type: ignore
    except ImportError:
        return "Установи psutil."
    mem = psutil.virtual_memory()
    used_gb = (mem.total - mem.available) / (1024 ** 3)
    total_gb = mem.total / (1024 ** 3)
    return f"Память: занято {used_gb:.1f} из {total_gb:.1f} гигабайт, {mem.percent:.0f} процентов."


def _say_disk(_m, _t):
    try:
        import psutil  # type: ignore
    except ImportError:
        return "Установи psutil."
    import platform
    path = "C:\\" if platform.system().lower() == "windows" else "/"
    usage = psutil.disk_usage(path)
    free_gb = usage.free / (1024 ** 3)
    total_gb = usage.total / (1024 ** 3)
    return (
        f"Диск {path}: свободно {free_gb:.0f} из {total_gb:.0f} гигабайт, "
        f"занято {usage.percent:.0f} процентов."
    )


def _say_battery(_m, _t):
    try:
        import psutil  # type: ignore
    except ImportError:
        return "Установи psutil."
    bat = psutil.sensors_battery()
    if bat is None:
        return "Батарея не обнаружена — похоже, это стационарный компьютер."
    status = "заряжается" if bat.power_plugged else "разряжается"
    return f"Батарея {bat.percent:.0f} процентов, {status}."


def _say_status(_m, _t):
    parts = [_say_cpu(None, None), _say_ram(None, None)]
    with contextlib.suppress(Exception):
        parts.append(_say_battery(None, None))
    return " ".join(parts)


def intents() -> list[Intent]:
    return [
        Intent(
            name="cpu",
            patterns=compile_patterns([
                r"\b(загрузка|использование)\s+(процессора|цпу|cpu)\b",
                r"\bкак\s+(нагружен|загружен)\s+процессор\b",
                r"\bсколько\s+процессор\b",
            ]),
            handler=_say_cpu,
            priority=25,
        ),
        Intent(
            name="ram",
            patterns=compile_patterns([
                r"\b(сколько|занято)\s+(оперативной\s+памяти|оперативки|памяти|рам|ram)\b",
                r"\bзагрузка\s+(памяти|оперативки)\b",
            ]),
            handler=_say_ram,
            priority=25,
        ),
        Intent(
            name="disk",
            patterns=compile_patterns([
                r"\b(сколько\s+(места|свободного\s+места)|свободно\s+на\s+диске)\b",
                r"\bзагрузка\s+диска\b",
            ]),
            handler=_say_disk,
            priority=25,
        ),
        Intent(
            name="battery",
            patterns=compile_patterns([
                r"\b(сколько|уровень)\s+(заряда|батареи|батарейки)\b",
                r"\bсостояние\s+батареи\b",
            ]),
            handler=_say_battery,
            priority=25,
        ),
        Intent(
            name="status",
            patterns=compile_patterns([
                r"\bсостояние\s+(компьютера|системы|пк)\b",
                r"\bкак\s+дела\s+у\s+компьютера\b",
                r"\bстатус\s+системы\b",
            ]),
            handler=_say_status,
            priority=25,
        ),
    ]
