"""Питание: блокировка, сон, выключение, перезагрузка."""
from __future__ import annotations

import ctypes
import platform
import subprocess

from ..logger import get_logger
from ..router import Intent, compile_patterns

log = get_logger("skills.power")


def _system() -> str:
    return platform.system().lower()


def _lock() -> str:
    sys = _system()
    if sys == "windows":
        try:
            ctypes.windll.user32.LockWorkStation()  # type: ignore[attr-defined]
            return "Блокирую компьютер."
        except Exception as exc:  # pragma: no cover
            return f"Не удалось заблокировать: {exc}"
    if sys == "darwin":
        try:
            subprocess.run(
                ["pmset", "displaysleepnow"],
                check=True,
            )
            return "Блокирую компьютер."
        except Exception:
            return "Не удалось заблокировать."
    # Linux: пробуем несколько утилит.
    for cmd in (
        ["loginctl", "lock-session"],
        ["xdg-screensaver", "lock"],
        ["gnome-screensaver-command", "-l"],
    ):
        try:
            subprocess.run(cmd, check=True)
            return "Блокирую компьютер."
        except Exception:
            continue
    return "Не нашёл способ заблокировать сессию."


def _shutdown() -> str:
    sys = _system()
    try:
        if sys == "windows":
            subprocess.Popen(["shutdown", "/s", "/t", "30"])
            return "Выключаю компьютер через 30 секунд. Скажи «отмени выключение», чтобы отменить."
        if sys == "darwin":
            subprocess.Popen(["osascript", "-e", 'tell app "System Events" to shut down'])
            return "Выключаю компьютер."
        subprocess.Popen(["shutdown", "-h", "+1"])
        return "Выключаю компьютер через минуту."
    except Exception as exc:  # pragma: no cover
        return f"Не удалось выключить: {exc}"


def _cancel_shutdown() -> str:
    sys = _system()
    try:
        if sys == "windows":
            subprocess.run(["shutdown", "/a"], check=False)
        else:
            subprocess.run(["shutdown", "-c"], check=False)
        return "Выключение отменено."
    except Exception as exc:  # pragma: no cover
        return f"Не удалось отменить: {exc}"


def _reboot() -> str:
    sys = _system()
    try:
        if sys == "windows":
            subprocess.Popen(["shutdown", "/r", "/t", "30"])
            return "Перезагружаю через 30 секунд."
        if sys == "darwin":
            subprocess.Popen(["osascript", "-e", 'tell app "System Events" to restart'])
            return "Перезагружаю компьютер."
        subprocess.Popen(["shutdown", "-r", "+1"])
        return "Перезагружаю через минуту."
    except Exception as exc:  # pragma: no cover
        return f"Не удалось перезагрузить: {exc}"


def _sleep() -> str:
    sys = _system()
    try:
        if sys == "windows":
            subprocess.Popen(
                ["rundll32.exe", "powrprof.dll,SetSuspendState", "Sleep"],
            )
            return "Усыпляю компьютер."
        if sys == "darwin":
            subprocess.Popen(["pmset", "sleepnow"])
            return "Усыпляю компьютер."
        subprocess.Popen(["systemctl", "suspend"])
        return "Усыпляю компьютер."
    except Exception as exc:  # pragma: no cover
        return f"Не удалось перевести в сон: {exc}"


def intents() -> list[Intent]:
    return [
        Intent(
            name="lock",
            patterns=compile_patterns([
                r"\bзаблокируй\s+(?:компьютер|систему|пк|экран)?\b",
                r"\bзалочь\b",
            ]),
            handler=lambda _m, _t: _lock(),
            priority=40,
        ),
        Intent(
            name="shutdown",
            patterns=compile_patterns([
                r"\bвыключи\s+(?:компьютер|пк|систему)\b",
                r"\bвырубай\s+(?:компьютер|пк|систему)\b",
            ]),
            handler=lambda _m, _t: _shutdown(),
            priority=40,
        ),
        Intent(
            name="cancel_shutdown",
            patterns=compile_patterns([
                r"\bотмени\s+выключение\b",
                r"\bне выключай\b",
            ]),
            handler=lambda _m, _t: _cancel_shutdown(),
            priority=45,
        ),
        Intent(
            name="reboot",
            patterns=compile_patterns([
                r"\bперезагрузи\s+(?:компьютер|пк|систему)?\b",
                r"\bребутни\b",
            ]),
            handler=lambda _m, _t: _reboot(),
            priority=40,
        ),
        Intent(
            name="sleep",
            patterns=compile_patterns([
                r"\b(?:усыпи|режим сна|отправь в сон)\s*(?:компьютер|пк|систему)?\b",
            ]),
            handler=lambda _m, _t: _sleep(),
            priority=40,
        ),
    ]
