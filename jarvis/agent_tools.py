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
# УПРАВЛЕНИЕ ОКНАМИ (Windows: ctypes user32; на других ОС — best effort)
# ---------------------------------------------------------------------------


def _is_windows() -> bool:
    return platform.system().lower() == "windows"


def _enum_windows() -> list[dict[str, Any]]:
    """Возвращает список видимых окон Windows: [{hwnd, title, pid}]."""
    if not _is_windows():
        return []
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return []

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    EnumWindows = user32.EnumWindows
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    GetWindowText = user32.GetWindowTextW
    GetWindowTextLength = user32.GetWindowTextLengthW
    IsWindowVisible = user32.IsWindowVisible
    GetWindowThreadProcessId = user32.GetWindowThreadProcessId

    windows: list[dict[str, Any]] = []

    def _cb(hwnd, _lparam):  # type: ignore[no-untyped-def]
        if not IsWindowVisible(hwnd):
            return True
        length = GetWindowTextLength(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        GetWindowText(hwnd, buf, length + 1)
        title = buf.value.strip()
        if not title:
            return True
        pid = wintypes.DWORD()
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        windows.append({"hwnd": int(hwnd), "title": title, "pid": int(pid.value)})
        return True

    EnumWindows(EnumWindowsProc(_cb), 0)
    return windows


def _find_window_hwnd(title_substr: str | None) -> int | None:
    """Возвращает hwnd подходящего окна. None = активное окно."""
    if not _is_windows():
        return None
    import ctypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    if not title_substr:
        hwnd = int(user32.GetForegroundWindow())
        return hwnd or None
    needle = title_substr.strip().lower()
    for w in _enum_windows():
        if needle in w["title"].lower():
            return int(w["hwnd"])
    return None


def list_windows() -> dict:
    """Возвращает список открытых окон с заголовками и PID."""
    if not _is_windows():
        return {"ok": False, "error": "Только Windows"}
    wins = _enum_windows()
    return {"ok": True, "count": len(wins), "windows": wins[:50]}


def _show_window(title_substr: str | None, cmd: int, action: str) -> dict:
    if not _is_windows():
        return {"ok": False, "error": "Только Windows"}
    hwnd = _find_window_hwnd(title_substr)
    if not hwnd:
        return {"ok": False, "error": f"окно не найдено: {title_substr or 'активное'}"}
    try:
        import ctypes

        ctypes.windll.user32.ShowWindow(hwnd, cmd)  # type: ignore[attr-defined]
        return {"ok": True, "action": action, "hwnd": hwnd}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def minimize_window(title_substr: str | None = None) -> dict:
    """Сворачивает окно по подстроке заголовка. Без аргумента — активное.

    Args:
        title_substr: часть заголовка окна (например, «chrome», «блокнот»).
    """
    return _show_window(title_substr, 6, "minimize")  # SW_MINIMIZE = 6


def maximize_window(title_substr: str | None = None) -> dict:
    """Разворачивает окно на весь экран. Без аргумента — активное.

    Args:
        title_substr: часть заголовка окна.
    """
    return _show_window(title_substr, 3, "maximize")  # SW_MAXIMIZE = 3


def restore_window(title_substr: str | None = None) -> dict:
    """Восстанавливает окно (из свёрнутого/развёрнутого в нормальное).

    Args:
        title_substr: часть заголовка окна.
    """
    return _show_window(title_substr, 9, "restore")  # SW_RESTORE = 9


def focus_window(title_substr: str) -> dict:
    """Переключает фокус на окно по подстроке заголовка.

    Args:
        title_substr: часть заголовка окна (например, «vs code», «youtube»).
    """
    if not _is_windows():
        return {"ok": False, "error": "Только Windows"}
    hwnd = _find_window_hwnd(title_substr)
    if not hwnd:
        return {"ok": False, "error": f"окно не найдено: {title_substr}"}
    try:
        import ctypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        # Если окно свёрнуто, сначала восстановим.
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        return {"ok": True, "hwnd": hwnd}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def close_window(title_substr: str | None = None) -> dict:
    """Закрывает окно через WM_CLOSE (приложение само отработает диалоги сохранения).

    Args:
        title_substr: часть заголовка окна. Без аргумента — активное.
    """
    if not _is_windows():
        return {"ok": False, "error": "Только Windows"}
    hwnd = _find_window_hwnd(title_substr)
    if not hwnd:
        return {"ok": False, "error": f"окно не найдено: {title_substr or 'активное'}"}
    if not _confirm("close_window", f"hwnd={hwnd}, title~{title_substr or 'активное'}"):
        return {"ok": False, "error": "Отказано пользователем"}
    try:
        import ctypes

        WM_CLOSE = 0x0010
        ctypes.windll.user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)  # type: ignore[attr-defined]
        return {"ok": True, "hwnd": hwnd}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def minimize_all() -> dict:
    """Сворачивает все окна (эквивалент Win+D — показать рабочий стол)."""
    if not _is_windows():
        return {"ok": False, "error": "Только Windows"}
    try:
        import pyautogui  # type: ignore

        pyautogui.hotkey("win", "d")
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def get_active_window() -> dict:
    """Возвращает заголовок и PID активного окна."""
    if not _is_windows():
        return {"ok": False, "error": "Только Windows"}
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        hwnd = int(user32.GetForegroundWindow())
        if not hwnd:
            return {"ok": False, "error": "нет активного окна"}
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return {"ok": True, "hwnd": hwnd, "title": buf.value, "pid": int(pid.value)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# МЫШЬ
# ---------------------------------------------------------------------------


def move_cursor(x: int, y: int, duration: float = 0.2) -> dict:
    """Плавно перемещает курсор в точку (x, y) на экране.

    Args:
        x: координата X в пикселях.
        y: координата Y в пикселях.
        duration: продолжительность движения в секундах.
    """
    try:
        import pyautogui  # type: ignore

        pyautogui.moveTo(x, y, duration=max(0.0, duration))
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def click_at(x: int | None = None, y: int | None = None, button: str = "left", clicks: int = 1) -> dict:
    """Кликает в точку. Без координат — в текущей позиции курсора.

    Args:
        x: координата X (опционально).
        y: координата Y (опционально).
        button: 'left' | 'right' | 'middle'.
        clicks: количество кликов (1 для одиночного, 2 для двойного).
    """
    try:
        import pyautogui  # type: ignore

        kwargs: dict[str, Any] = {"button": button, "clicks": max(1, clicks)}
        if x is not None and y is not None:
            kwargs["x"] = x
            kwargs["y"] = y
        pyautogui.click(**kwargs)
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def scroll(amount: int) -> dict:
    """Прокручивает колесо мыши. Положительное число — вверх, отрицательное — вниз.

    Args:
        amount: количество «щелчков» колеса (например, 5 или -10).
    """
    try:
        import pyautogui  # type: ignore

        pyautogui.scroll(amount)
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def get_screen_size() -> dict:
    """Возвращает разрешение экрана (width, height)."""
    try:
        import pyautogui  # type: ignore

        w, h = pyautogui.size()
        return {"ok": True, "width": int(w), "height": int(h)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# БУФЕР ОБМЕНА
# ---------------------------------------------------------------------------


def copy_to_clipboard(text: str) -> dict:
    """Копирует текст в системный буфер обмена.

    Args:
        text: текст для копирования.
    """
    if _is_windows():
        try:
            proc = subprocess.run(["clip"], input=text, text=True, timeout=5, check=False)
            return {"ok": proc.returncode == 0, "chars": len(text)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
    # Unix fallback
    for cmd in (["xclip", "-selection", "clipboard"], ["wl-copy"], ["pbcopy"]):
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, input=text, text=True, timeout=5, check=False)
                return {"ok": True, "chars": len(text)}
            except Exception:
                continue
    return {"ok": False, "error": "буфер обмена недоступен"}


def read_clipboard() -> dict:
    """Читает текст из буфера обмена."""
    if _is_windows():
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=5,
            )
            return {"ok": True, "text": proc.stdout.rstrip("\r\n")}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
    for cmd in (["xclip", "-selection", "clipboard", "-o"], ["wl-paste"], ["pbpaste"]):
        if shutil.which(cmd[0]):
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                return {"ok": True, "text": proc.stdout}
            except Exception:
                continue
    return {"ok": False, "error": "буфер обмена недоступен"}


# ---------------------------------------------------------------------------
# УВЕДОМЛЕНИЯ
# ---------------------------------------------------------------------------


def show_notification(title: str, message: str = "") -> dict:
    """Показывает всплывающее уведомление Windows в системном трее.

    Args:
        title: заголовок уведомления.
        message: текст уведомления.
    """
    if _is_windows():
        try:
            ps = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$n = New-Object System.Windows.Forms.NotifyIcon; "
                "$n.Icon = [System.Drawing.SystemIcons]::Information; "
                "$n.Visible = $true; "
                f"$n.ShowBalloonTip(5000, {repr(title)}, {repr(message)}, "
                "[System.Windows.Forms.ToolTipIcon]::Info); "
                "Start-Sleep -Seconds 5; $n.Dispose()"
            )
            subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps])
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
    return {"ok": False, "error": "Уведомления реализованы только под Windows"}


# ---------------------------------------------------------------------------
# WEB FETCH
# ---------------------------------------------------------------------------


def fetch_url(url: str, max_chars: int = 4000) -> dict:
    """Загружает страницу по URL и возвращает её текст (без HTML-тегов).

    Args:
        url: полный URL (https://...).
        max_chars: максимум символов в возвращаемом тексте.
    """
    try:
        import re

        import requests  # type: ignore

        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 Jarvis"})
        resp.raise_for_status()
        html = resp.text
        # Грубо вырезаем теги/скрипты.
        text = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return {"ok": True, "url": url, "title": "", "text": text[:max_chars]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# ОЖИДАНИЕ
# ---------------------------------------------------------------------------


def sleep(seconds: float) -> dict:
    """Ждёт указанное число секунд (полезно между действиями GUI).

    Args:
        seconds: сколько ждать (максимум 30).
    """
    import time

    secs = max(0.0, min(30.0, float(seconds)))
    time.sleep(secs)
    return {"ok": True, "waited": secs}


# ---------------------------------------------------------------------------
# Список инструментов, передаваемый в Gemini
# ---------------------------------------------------------------------------

ALL_TOOLS = [
    # Запуск приложений и сайтов
    open_app,
    open_url,
    search_web,
    fetch_url,
    # Звук / яркость / экран
    set_volume,
    set_mute,
    set_brightness,
    take_screenshot,
    # Окна
    list_windows,
    get_active_window,
    focus_window,
    minimize_window,
    maximize_window,
    restore_window,
    close_window,
    minimize_all,
    # Клавиатура / мышь
    type_text,
    press_keys,
    click_at,
    move_cursor,
    scroll,
    get_screen_size,
    # Буфер обмена
    copy_to_clipboard,
    read_clipboard,
    # Файлы / shell / python
    system_info,
    read_file,
    list_dir,
    write_file,
    run_shell,
    run_python,
    # Уведомления, ожидание
    show_notification,
    sleep,
    # Питание
    lock_workstation,
    shutdown_pc,
    cancel_shutdown,
]


_ = os  # silence unused
