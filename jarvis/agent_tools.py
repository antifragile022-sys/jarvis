"""Инструменты для агент-режима Gemini.

Каждая функция — это python-callable, которую SDK передаёт модели как «tool».
SDK сам читает type hints и docstring → автогенерирует function declaration.

Опасные действия (`run_shell`, `run_python`, `write_file`, выключения)
требуют подтверждения через Tk-диалог, если в настройках не включён `auto_approve`.
"""
from __future__ import annotations

import contextlib
import os
import platform
import shutil
import subprocess
import textwrap
import urllib.parse
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

from .logger import get_logger
from .skills import apps as apps_skill
from .skills import brightness as brightness_skill
from .skills import volume as volume_skill

log = get_logger("agent.tools")

# -- глобальный флаг auto-approve (выставляется при старте ассистента) ---------
_AUTO_APPROVE = False
_SCREENSHOTS_DIR: Path | None = None


def configure(auto_approve: bool, screenshots_dir: Path | None = None) -> None:
    global _AUTO_APPROVE, _SCREENSHOTS_DIR
    _AUTO_APPROVE = bool(auto_approve)
    _SCREENSHOTS_DIR = Path(screenshots_dir) if screenshots_dir else None


def _confirm(action: str, details: str) -> bool:
    """Показывает Tk-диалог подтверждения. В headless / на CI — возвращает auto_approve."""
    if _AUTO_APPROVE:
        log.info("auto-approve: %s — %s", action, details[:200])
        return True
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        ok = messagebox.askyesno(
            "Jarvis · Подтверждение",
            f"Джарвис хочет выполнить:\n\n[{action}]\n\n{details[:1500]}\n\nРазрешить?",
        )
        with contextlib.suppress(Exception):
            root.destroy()
        return bool(ok)
    except Exception as exc:
        log.warning("Не смог показать диалог подтверждения: %s — отказ.", exc)
        return False


# ---------------------------------------------------------------------------
# БЕЗОПАСНЫЕ ИНСТРУМЕНТЫ (не требуют подтверждения)
# ---------------------------------------------------------------------------


def open_app(name: str) -> dict:
    """Запускает приложение на компьютере по короткому имени.

    Args:
        name: короткое имя — «браузер», «блокнот», «калькулятор», «вс код»,
              «терминал», «эксель», «outlook», или полное имя исполняемого файла.

    Returns:
        Словарь со статусом запуска.
    """
    requested = name.lower().strip()
    candidates = apps_skill.APP_ALIASES.get(requested, (requested,))
    launched = apps_skill._try_launch(candidates)  # noqa: SLF001
    return {"ok": bool(launched), "launched": launched or "", "requested": requested}


def open_url(url: str) -> dict:
    """Открывает URL в браузере по умолчанию.

    Args:
        url: полный URL, например https://example.com
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url, new=2)
    return {"ok": True, "url": url}


def search_web(query: str) -> dict:
    """Ищет запрос в Google в браузере по умолчанию.

    Args:
        query: текст поискового запроса.
    """
    url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
    webbrowser.open(url, new=2)
    return {"ok": True, "query": query, "url": url}


def set_volume(percent: int) -> dict:
    """Устанавливает громкость системы.

    Args:
        percent: целое от 0 до 100.
    """
    pct = max(0, min(int(percent), 100))
    ok = volume_skill.set_volume(pct)
    return {"ok": ok, "volume": pct}


def set_mute(mute: bool) -> dict:
    """Включает/выключает беззвучный режим.

    Args:
        mute: True — выключить звук, False — включить.
    """
    ok = volume_skill.set_mute(bool(mute))
    return {"ok": ok, "muted": bool(mute)}


def set_brightness(percent: int) -> dict:
    """Устанавливает яркость экрана.

    Args:
        percent: целое от 0 до 100.
    """
    pct = max(0, min(int(percent), 100))
    try:
        import screen_brightness_control as sbc  # type: ignore

        sbc.set_brightness(pct)
        return {"ok": True, "brightness": pct}
    except Exception as exc:
        log.warning("brightness failed: %s", exc)
        return {"ok": False, "error": str(exc)}
    finally:
        _ = brightness_skill  # silence unused import


def take_screenshot() -> dict:
    """Делает скриншот экрана и сохраняет в файл.

    Returns:
        Путь до сохранённого файла.
    """
    try:
        try:
            import mss  # type: ignore
            import mss.tools  # type: ignore
        except ImportError:
            import pyautogui  # type: ignore

            mss = None  # type: ignore[assignment]
        out_dir = _SCREENSHOTS_DIR or (Path.home() / "Pictures" / "Jarvis")
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
        path = out_dir / filename

        if "mss" in dir() and mss is not None:
            with mss.mss() as sct:  # type: ignore[attr-defined]
                # primary monitor (index 1)
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                shot = sct.grab(monitor)
                mss.tools.to_png(shot.rgb, shot.size, output=str(path))  # type: ignore[attr-defined]
        else:
            import pyautogui  # type: ignore

            pyautogui.screenshot().save(str(path))

        return {"ok": True, "path": str(path)}
    except Exception as exc:
        log.error("screenshot failed: %s", exc)
        return {"ok": False, "error": str(exc)}


def system_info() -> dict:
    """Возвращает текущую загрузку CPU, памяти, диска и статус батареи."""
    info: dict[str, Any] = {}
    try:
        import psutil  # type: ignore

        info["cpu_percent"] = psutil.cpu_percent(interval=0.3)
        mem = psutil.virtual_memory()
        info["memory"] = {
            "total_gb": round(mem.total / 1024 ** 3, 2),
            "used_gb": round((mem.total - mem.available) / 1024 ** 3, 2),
            "percent": mem.percent,
        }
        disk = psutil.disk_usage("C:\\" if platform.system() == "Windows" else "/")
        info["disk"] = {
            "total_gb": round(disk.total / 1024 ** 3, 2),
            "free_gb": round(disk.free / 1024 ** 3, 2),
            "percent": disk.percent,
        }
        battery = psutil.sensors_battery()
        if battery is not None:
            info["battery"] = {
                "percent": battery.percent,
                "plugged": bool(battery.power_plugged),
            }
    except ImportError:
        info["error"] = "psutil не установлен"
    info["os"] = platform.platform()
    info["time"] = datetime.now().isoformat(timespec="seconds")
    return info


def read_file(path: str, max_chars: int = 4000) -> dict:
    """Читает текстовый файл (UTF-8) и возвращает содержимое.

    Args:
        path: путь к файлу.
        max_chars: максимум символов (большие файлы обрезаются).
    """
    p = Path(path).expanduser()
    if not p.exists():
        return {"ok": False, "error": f"Файл не найден: {p}"}
    try:
        data = p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    truncated = len(data) > max_chars
    return {
        "ok": True,
        "path": str(p),
        "content": data[:max_chars],
        "truncated": truncated,
        "size": len(data),
    }


def list_dir(path: str = ".") -> dict:
    """Перечисляет файлы в директории.

    Args:
        path: путь до директории (по умолчанию текущая).
    """
    p = Path(path).expanduser()
    if not p.exists() or not p.is_dir():
        return {"ok": False, "error": f"Не директория: {p}"}
    entries = []
    for child in sorted(p.iterdir()):
        entries.append({
            "name": child.name,
            "is_dir": child.is_dir(),
            "size": child.stat().st_size if child.is_file() else None,
        })
    return {"ok": True, "path": str(p.resolve()), "entries": entries[:200]}


# ---------------------------------------------------------------------------
# ОПАСНЫЕ ИНСТРУМЕНТЫ (требуют подтверждения)
# ---------------------------------------------------------------------------


def write_file(path: str, content: str, append: bool = False) -> dict:
    """Создаёт или дописывает текстовый файл.

    Args:
        path: путь к файлу.
        content: содержимое в виде строки (UTF-8).
        append: если True — дописывает в конец; иначе перезаписывает.
    """
    p = Path(path).expanduser()
    mode = "a" if append else "w"
    if not _confirm(
        "write_file",
        f"Файл: {p}\nРежим: {'дописать' if append else 'перезаписать'}\n"
        f"Размер: {len(content)} символов\n\nНачало:\n{content[:500]}",
    ):
        return {"ok": False, "error": "Отказано пользователем"}
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open(mode, encoding="utf-8") as f:
            f.write(content)
        return {"ok": True, "path": str(p), "bytes": len(content.encode("utf-8"))}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def run_shell(command: str, timeout: int = 60) -> dict:
    """Выполняет команду в системной оболочке (PowerShell на Windows, sh на Unix).

    Args:
        command: команда оболочки.
        timeout: максимум секунд ожидания (по умолчанию 60).
    """
    if not _confirm("run_shell", f"Команда:\n{command}"):
        return {"ok": False, "error": "Отказано пользователем"}
    is_win = platform.system().lower() == "windows"
    try:
        if is_win:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True, text=True, timeout=timeout,
            )
        else:
            proc = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout,
            )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-2000:],
            "stderr": proc.stderr[-2000:],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def run_python(code: str, timeout: int = 30) -> dict:
    """Выполняет Python-код в подпроцессе и возвращает stdout/stderr.

    Args:
        code: исходный код на Python 3.
        timeout: максимум секунд ожидания.
    """
    code = textwrap.dedent(code)
    if not _confirm("run_python", code):
        return {"ok": False, "error": "Отказано пользователем"}
    try:
        proc = subprocess.run(
            ["python", "-I", "-c", code],
            capture_output=True, text=True, timeout=timeout,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-2000:],
            "stderr": proc.stderr[-2000:],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def type_text(text: str, interval: float = 0.02) -> dict:
    """Эмулирует ввод текста с клавиатуры в активное окно.

    Args:
        text: текст для набора.
        interval: задержка между символами в секундах.
    """
    if not _confirm("type_text", f"Текст:\n{text[:300]}"):
        return {"ok": False, "error": "Отказано пользователем"}
    try:
        import pyautogui  # type: ignore

        pyautogui.write(text, interval=interval)
        return {"ok": True, "chars": len(text)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def press_keys(keys: str) -> dict:
    """Нажимает комбинацию клавиш через pyautogui.hotkey.

    Args:
        keys: комбинация через '+', например 'ctrl+c' или 'win+d'.
    """
    if not _confirm("press_keys", keys):
        return {"ok": False, "error": "Отказано пользователем"}
    parts = [p.strip().lower() for p in keys.split("+") if p.strip()]
    if not parts:
        return {"ok": False, "error": "пустая комбинация"}
    try:
        import pyautogui  # type: ignore

        pyautogui.hotkey(*parts)
        return {"ok": True, "keys": parts}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def lock_workstation() -> dict:
    """Блокирует сеанс пользователя."""
    if platform.system().lower() == "windows":
        try:
            import ctypes

            ctypes.windll.user32.LockWorkStation()  # type: ignore[attr-defined]
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
    # Unix-альтернативы
    for cmd in (
        ["loginctl", "lock-session"],
        ["xdg-screensaver", "lock"],
    ):
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, check=True)
                return {"ok": True}
            except Exception:
                continue
    return {"ok": False, "error": "не найден способ заблокировать"}


def shutdown_pc(delay_seconds: int = 30) -> dict:
    """Выключает компьютер с задержкой.

    Args:
        delay_seconds: секунд до выключения (даёт окно для отмены).
    """
    if not _confirm("shutdown", f"Через {delay_seconds} секунд"):
        return {"ok": False, "error": "Отказано пользователем"}
    is_win = platform.system().lower() == "windows"
    try:
        if is_win:
            subprocess.Popen(["shutdown", "/s", "/t", str(delay_seconds)])
        else:
            subprocess.Popen(["shutdown", "-h", f"+{max(1, delay_seconds // 60)}"])
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def cancel_shutdown() -> dict:
    """Отменяет ранее запланированное выключение."""
    is_win = platform.system().lower() == "windows"
    try:
        subprocess.run(["shutdown", "/a" if is_win else "-c"], check=False)
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Список инструментов, передаваемый в Gemini
# ---------------------------------------------------------------------------

ALL_TOOLS = [
    open_app,
    open_url,
    search_web,
    set_volume,
    set_mute,
    set_brightness,
    take_screenshot,
    system_info,
    read_file,
    list_dir,
    write_file,
    run_shell,
    run_python,
    type_text,
    press_keys,
    lock_workstation,
    shutdown_pc,
    cancel_shutdown,
]


_ = os  # silence unused
