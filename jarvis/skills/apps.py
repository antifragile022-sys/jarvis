"""Запуск приложений по голосовой команде."""
from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from collections.abc import Iterable

from ..logger import get_logger
from ..router import Intent, compile_patterns

log = get_logger("skills.apps")

# Алиас → список кандидатов для запуска.
# На Windows os.startfile() умеет открывать по имени (если приложение в PATH или зарегистрировано).
APP_ALIASES: dict[str, tuple[str, ...]] = {
    "браузер": ("chrome", "msedge", "firefox", "iexplore"),
    "хром": ("chrome",),
    "гугл хром": ("chrome",),
    "эдж": ("msedge",),
    "файрфокс": ("firefox",),
    "блокнот": ("notepad",),
    "калькулятор": ("calc",),
    "проводник": ("explorer",),
    "терминал": ("wt", "powershell", "cmd"),
    "командная строка": ("cmd",),
    "повершелл": ("powershell", "pwsh"),
    "пейнт": ("mspaint",),
    "ворд": ("winword",),
    "эксель": ("excel",),
    "повер пойнт": ("powerpnt",),
    "outlook": ("outlook",),
    "почта": ("outlook",),
    "телеграм": ("telegram", "Telegram"),
    "телега": ("telegram", "Telegram"),
    "дискорд": ("discord", "Discord"),
    "стим": ("steam",),
    "spotify": ("spotify",),
    "спотифай": ("spotify",),
    "vs code": ("code",),
    "вс код": ("code",),
    "вскод": ("code",),
    "вижуал студио код": ("code",),
    "обс": ("obs64", "obs"),
    "obs": ("obs64", "obs"),
}


def _try_launch(candidates: Iterable[str]) -> str | None:
    """Пытается запустить первое доступное приложение из списка кандидатов.

    Возвращает имя запущенного приложения или None.
    """
    system = platform.system().lower()
    for name in candidates:
        # На Windows os.startfile умеет найти приложение даже без полного пути.
        if system == "windows":
            try:
                import os

                os.startfile(name)  # type: ignore[attr-defined]
                log.info("Запустил через os.startfile: %s", name)
                return name
            except OSError as exc:
                log.debug("os.startfile(%s) не сработал: %s", name, exc)
            # Резерв: subprocess через `start`.
            if shutil.which(name) or shutil.which(f"{name}.exe"):
                try:
                    subprocess.Popen([name], shell=False)
                    log.info("Запустил через subprocess: %s", name)
                    return name
                except OSError as exc:
                    log.debug("subprocess(%s) не сработал: %s", name, exc)
        else:
            path = shutil.which(name)
            if path:
                try:
                    subprocess.Popen([path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    log.info("Запустил: %s", path)
                    return name
                except OSError as exc:
                    log.debug("subprocess(%s) не сработал: %s", name, exc)
    return None


def _open_app(m, _phrase: str) -> str:
    requested = (m.group("app") or "").strip().lower()
    if not requested:
        return "Какое приложение открыть?"

    # Точные совпадения.
    candidates = APP_ALIASES.get(requested)
    if candidates is None:
        # Частичное совпадение по ключу.
        for alias, cands in APP_ALIASES.items():
            if alias in requested or requested in alias:
                candidates = cands
                break

    if candidates is None:
        # Пробуем напрямую как имя исполняемого файла.
        candidates = (requested,)

    launched = _try_launch(candidates)
    if launched:
        return f"Открываю {requested}."
    return f"Не нашёл приложение «{requested}»."


def _close_app(m, _phrase: str) -> str:
    requested = (m.group("app") or "").strip().lower()
    if not requested:
        return "Какое приложение закрыть?"

    # Берём первое сопоставление как имя процесса.
    candidates = APP_ALIASES.get(requested, (requested,))
    process_name = candidates[0]

    system = platform.system().lower()
    if system == "windows":
        result = subprocess.run(
            ["taskkill", "/F", "/IM", f"{process_name}.exe"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return f"Закрываю {requested}."
        return f"Не получилось закрыть {requested}."
    else:
        try:
            subprocess.run(["pkill", "-f", process_name], check=False)
            return f"Закрываю {requested}."
        except FileNotFoundError:
            return "Закрытие приложений не поддерживается на этой системе."


# Грубый шаблон: «открой/запусти/включи <app>», где <app> — всё после ключевого слова.
_OPEN_PATTERNS = [
    r"\b(?:открой|открыть|запусти|запустить|включи|включить|открывай)\s+(?P<app>[\w\s\-]+?)\s*$",
]
_CLOSE_PATTERNS = [
    r"\b(?:закрой|закрыть|выключи|выключить|останови)\s+(?:приложение\s+)?(?P<app>[\w\s\-]+?)\s*$",
]


def intents() -> list[Intent]:
    return [
        Intent(
            name="open_app",
            patterns=compile_patterns(_OPEN_PATTERNS),
            handler=_open_app,
            priority=5,
        ),
        Intent(
            name="close_app",
            patterns=compile_patterns(_CLOSE_PATTERNS),
            handler=_close_app,
            priority=5,
        ),
    ]


_ = sys  # keep import for potential future use
