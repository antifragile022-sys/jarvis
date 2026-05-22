"""Управление громкостью.

На Windows — через pycaw (Core Audio API).
На macOS — через `osascript`.
На Linux — через `amixer` или `pactl`, если доступны.
"""
from __future__ import annotations

import platform
import re
import shutil
import subprocess

from ..logger import get_logger
from ..router import Intent, compile_patterns

log = get_logger("skills.volume")


def _system() -> str:
    return platform.system().lower()


# ---------- Windows (pycaw) ----------

def _windows_get_volume_pct() -> int | None:
    try:
        from comtypes import CLSCTX_ALL  # type: ignore
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore
    except ImportError:
        return None

    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = interface.QueryInterface(IAudioEndpointVolume)
        scalar = volume.GetMasterVolumeLevelScalar()
        return int(round(scalar * 100))
    except Exception as exc:  # pragma: no cover
        log.error("pycaw get failed: %s", exc)
        return None


def _windows_set_volume_pct(pct: int) -> bool:
    try:
        from comtypes import CLSCTX_ALL  # type: ignore
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore
    except ImportError:
        return False

    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = interface.QueryInterface(IAudioEndpointVolume)
        scalar = max(0.0, min(pct / 100.0, 1.0))
        volume.SetMasterVolumeLevelScalar(scalar, None)
        return True
    except Exception as exc:  # pragma: no cover
        log.error("pycaw set failed: %s", exc)
        return False


def _windows_set_mute(mute: bool) -> bool:
    try:
        from comtypes import CLSCTX_ALL  # type: ignore
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore
    except ImportError:
        return False
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = interface.QueryInterface(IAudioEndpointVolume)
        volume.SetMute(1 if mute else 0, None)
        return True
    except Exception as exc:  # pragma: no cover
        log.error("pycaw mute failed: %s", exc)
        return False


# ---------- macOS ----------

def _mac_set_volume(pct: int) -> bool:
    try:
        subprocess.run(
            ["osascript", "-e", f"set volume output volume {max(0, min(pct, 100))}"],
            check=True,
        )
        return True
    except Exception:
        return False


def _mac_set_mute(mute: bool) -> bool:
    try:
        subprocess.run(
            ["osascript", "-e", f"set volume output muted {'true' if mute else 'false'}"],
            check=True,
        )
        return True
    except Exception:
        return False


# ---------- Linux ----------

def _linux_set_volume(pct: int) -> bool:
    if shutil.which("pactl"):
        try:
            subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{max(0, min(pct, 100))}%"],
                check=True,
            )
            return True
        except Exception:
            pass
    if shutil.which("amixer"):
        try:
            subprocess.run(
                ["amixer", "-D", "pulse", "sset", "Master", f"{max(0, min(pct, 100))}%"],
                check=True,
            )
            return True
        except Exception:
            pass
    return False


def _linux_set_mute(mute: bool) -> bool:
    if shutil.which("pactl"):
        try:
            subprocess.run(
                ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if mute else "0"],
                check=True,
            )
            return True
        except Exception:
            pass
    return False


# ---------- Cross-platform façade ----------

def set_volume(pct: int) -> bool:
    sys = _system()
    if sys == "windows":
        return _windows_set_volume_pct(pct)
    if sys == "darwin":
        return _mac_set_volume(pct)
    return _linux_set_volume(pct)


def set_mute(mute: bool) -> bool:
    sys = _system()
    if sys == "windows":
        return _windows_set_mute(mute)
    if sys == "darwin":
        return _mac_set_mute(mute)
    return _linux_set_mute(mute)


def get_volume_pct() -> int | None:
    if _system() == "windows":
        return _windows_get_volume_pct()
    return None


# ---------- Handlers ----------

def _handle_set(m, _t):
    val = int(m.group("pct"))
    val = max(0, min(val, 100))
    if set_volume(val):
        return f"Громкость {val} процентов."
    return "Не удалось изменить громкость."


def _handle_up(_m, _t):
    cur = get_volume_pct()
    if cur is None:
        cur = 50
    new = min(cur + 10, 100)
    if set_volume(new):
        return f"Громче. Сейчас {new} процентов."
    return "Не удалось изменить громкость."


def _handle_down(_m, _t):
    cur = get_volume_pct()
    if cur is None:
        cur = 50
    new = max(cur - 10, 0)
    if set_volume(new):
        return f"Тише. Сейчас {new} процентов."
    return "Не удалось изменить громкость."


def _handle_mute(_m, _t):
    if set_mute(True):
        return "Звук выключен."
    return "Не удалось выключить звук."


def _handle_unmute(_m, _t):
    if set_mute(False):
        return "Звук включён."
    return "Не удалось включить звук."


def _handle_max(_m, _t):
    if set_volume(100):
        return "Громкость на максимум."
    return "Не удалось изменить громкость."


def intents() -> list[Intent]:
    return [
        Intent(
            name="volume_set",
            patterns=compile_patterns([
                r"\b(?:громкость|звук)\s+(?:на\s+)?(?P<pct>\d{1,3})\s*(?:процентов)?\b",
                r"\bсделай\s+громкость\s+(?P<pct>\d{1,3})\b",
                r"\bпоставь\s+громкость\s+(?:на\s+)?(?P<pct>\d{1,3})\b",
            ]),
            handler=_handle_set,
            priority=30,
        ),
        Intent(
            name="volume_up",
            patterns=compile_patterns([
                r"\b(?:сделай\s+)?(?:по)?громче\b",
                r"\bувеличь\s+громкость\b",
                r"\bприбавь\s+звук\b",
            ]),
            handler=_handle_up,
            priority=25,
        ),
        Intent(
            name="volume_down",
            patterns=compile_patterns([
                r"\b(?:сделай\s+)?(?:по)?тише\b",
                r"\bуменьши\s+громкость\b",
                r"\bубавь\s+звук\b",
            ]),
            handler=_handle_down,
            priority=25,
        ),
        Intent(
            name="mute",
            patterns=compile_patterns([
                r"\bвыключи\s+звук\b",
                r"\bотключи\s+звук\b",
                r"\bзаглуши\b",
                r"\bбез звука\b",
            ]),
            handler=_handle_mute,
            priority=30,
        ),
        Intent(
            name="unmute",
            patterns=compile_patterns([
                r"\bвключи\s+звук\b",
                r"\bверни\s+звук\b",
            ]),
            handler=_handle_unmute,
            priority=30,
        ),
        Intent(
            name="volume_max",
            patterns=compile_patterns([
                r"\bгромкость\s+(?:на\s+)?максимум\b",
                r"\bна полную громкость\b",
            ]),
            handler=_handle_max,
            priority=35,
        ),
    ]


_ = re  # for future use
