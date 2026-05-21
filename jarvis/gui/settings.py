"""Окно настроек на Tkinter.

Запускается:
  - при первом старте, если в config.json пуст gemini_api_key;
  - по команде «Джарвис, открой настройки» (или `jarvis settings`);
  - автоматически, когда Gemini вернул ошибку «квота исчерпана».
"""
from __future__ import annotations

import contextlib
from typing import Any

from ..logger import get_logger
from ..settings_store import DEFAULTS, get_settings_path, load_settings, save_settings

log = get_logger("gui.settings")


MODEL_OPTIONS = [
    "gemini-2.5-flash-lite",  # самая экономная
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-3.5-flash",
]


def _test_key(api_key: str, model: str) -> tuple[bool, str]:
    """Простой запрос к Gemini, чтобы проверить, что ключ рабочий."""
    api_key = (api_key or "").strip()
    if not api_key:
        return False, "Ключ пуст."
    try:
        from google import genai  # type: ignore
    except ImportError:
        return False, "Пакет google-genai не установлен."
    try:
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model or "gemini-2.5-flash-lite",
            contents="Скажи «ок» одним словом.",
        )
        text = (getattr(resp, "text", "") or "").strip()
        return True, f"OK · ответ: {text[:80]}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def open_settings_dialog(reason: str = "") -> dict[str, Any] | None:
    """Открывает модальное окно настроек.

    Args:
        reason: текст-причина (например, «квота исчерпана»), показывается сверху.

    Returns:
        Обновлённый словарь настроек, либо None если пользователь закрыл окно.
    """
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except ImportError:
        log.error("tkinter недоступен в этом интерпретаторе.")
        return None

    cur = load_settings()
    result: dict[str, Any] | None = None

    root = tk.Tk()
    root.title("Jarvis · Настройки")
    root.geometry("560x520")
    root.resizable(False, False)
    with contextlib.suppress(Exception):
        root.attributes("-topmost", True)

    main = ttk.Frame(root, padding=16)
    main.pack(fill="both", expand=True)

    row = 0
    if reason:
        warn = ttk.Label(
            main,
            text=reason,
            foreground="#a00",
            wraplength=520,
            justify="left",
        )
        warn.grid(row=row, column=0, columnspan=3, sticky="we", pady=(0, 10))
        row += 1

    title = ttk.Label(main, text="Настройки ассистента", font=("", 14, "bold"))
    title.grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 10))
    row += 1

    # --- API key ---
    ttk.Label(main, text="GEMINI_API_KEY:").grid(row=row, column=0, sticky="w", pady=4)
    key_var = tk.StringVar(value=cur.get("gemini_api_key", ""))
    key_entry = ttk.Entry(main, textvariable=key_var, width=42, show="•")
    key_entry.grid(row=row, column=1, sticky="we", pady=4)

    show_var = tk.BooleanVar(value=False)

    def _toggle_show():
        key_entry.config(show="" if show_var.get() else "•")

    ttk.Checkbutton(main, text="Показать", variable=show_var, command=_toggle_show).grid(
        row=row, column=2, sticky="w", padx=(6, 0)
    )
    row += 1

    hint = ttk.Label(
        main,
        text="Получить ключ: https://aistudio.google.com/app/apikey",
        foreground="#666",
    )
    hint.grid(row=row, column=0, columnspan=3, sticky="w")
    row += 1

    # --- Model ---
    ttk.Label(main, text="Модель Gemini:").grid(row=row, column=0, sticky="w", pady=(10, 4))
    model_var = tk.StringVar(value=cur.get("gemini_model", DEFAULTS["gemini_model"]))
    model_combo = ttk.Combobox(main, values=MODEL_OPTIONS, textvariable=model_var, state="readonly", width=40)
    model_combo.grid(row=row, column=1, columnspan=2, sticky="we", pady=(10, 4))
    row += 1

    # --- Wake words ---
    ttk.Label(main, text="Wake-word (через запятую):").grid(row=row, column=0, sticky="w", pady=4)
    wake_var = tk.StringVar(value=", ".join(cur.get("wake_words") or DEFAULTS["wake_words"]))
    ttk.Entry(main, textvariable=wake_var, width=42).grid(row=row, column=1, columnspan=2, sticky="we", pady=4)
    row += 1

    # --- TTS voice hint ---
    ttk.Label(main, text="TTS-голос (имя или часть):").grid(row=row, column=0, sticky="w", pady=4)
    voice_var = tk.StringVar(value=cur.get("tts_voice", ""))
    ttk.Entry(main, textvariable=voice_var, width=42).grid(row=row, column=1, columnspan=2, sticky="we", pady=4)
    row += 1

    # --- TTS rate ---
    ttk.Label(main, text="Скорость речи:").grid(row=row, column=0, sticky="w", pady=4)
    rate_var = tk.IntVar(value=int(cur.get("tts_rate", 180)))
    rate_scale = ttk.Scale(main, from_=120, to=260, orient="horizontal", variable=rate_var, length=240)
    rate_scale.grid(row=row, column=1, sticky="we", pady=4)
    rate_label = ttk.Label(main, text=str(rate_var.get()))
    rate_label.grid(row=row, column=2, sticky="w", padx=(6, 0))
    rate_var.trace_add("write", lambda *_: rate_label.config(text=str(int(rate_var.get()))))
    row += 1

    # --- City ---
    ttk.Label(main, text="Город по умолчанию (погода):").grid(row=row, column=0, sticky="w", pady=4)
    city_var = tk.StringVar(value=cur.get("default_city", "Москва"))
    ttk.Entry(main, textvariable=city_var, width=42).grid(row=row, column=1, columnspan=2, sticky="we", pady=4)
    row += 1

    # --- Mode ---
    ttk.Label(main, text="Режим:").grid(row=row, column=0, sticky="w", pady=(10, 4))
    agent_var = tk.BooleanVar(value=bool(cur.get("agent_mode", True)))
    ttk.Checkbutton(main, text="Агент-режим (Gemini может выполнять действия)", variable=agent_var).grid(
        row=row, column=1, columnspan=2, sticky="w", pady=(10, 4)
    )
    row += 1

    approve_var = tk.BooleanVar(value=bool(cur.get("auto_approve", False)))
    ttk.Checkbutton(
        main,
        text="Выполнять опасные действия без подтверждения (run_shell, run_python, write_file)",
        variable=approve_var,
    ).grid(row=row, column=1, columnspan=2, sticky="w", pady=4)
    row += 1

    # --- Status ---
    status_var = tk.StringVar(value="")
    status_label = ttk.Label(main, textvariable=status_var, foreground="#06c", wraplength=520)
    status_label.grid(row=row, column=0, columnspan=3, sticky="w", pady=(10, 4))
    row += 1

    # --- Buttons ---
    btns = ttk.Frame(main)
    btns.grid(row=row, column=0, columnspan=3, sticky="we", pady=(14, 0))
    btns.columnconfigure(3, weight=1)

    def _on_test():
        status_var.set("Проверяю ключ…")
        root.update_idletasks()
        ok, msg = _test_key(key_var.get(), model_var.get())
        status_label.config(foreground=("#0a0" if ok else "#a00"))
        status_var.set(msg)

    def _on_save():
        nonlocal result
        wake_list = [w.strip().lower() for w in wake_var.get().split(",") if w.strip()]
        if not wake_list:
            wake_list = list(DEFAULTS["wake_words"])
        new_settings = {
            **cur,
            "gemini_api_key": key_var.get().strip(),
            "gemini_model": model_var.get().strip() or DEFAULTS["gemini_model"],
            "wake_words": wake_list,
            "tts_voice": voice_var.get().strip(),
            "tts_rate": int(rate_var.get()),
            "default_city": city_var.get().strip() or DEFAULTS["default_city"],
            "agent_mode": bool(agent_var.get()),
            "auto_approve": bool(approve_var.get()),
        }
        try:
            save_settings(new_settings)
            result = new_settings
            messagebox.showinfo("Jarvis", f"Сохранено в {get_settings_path()}")
            root.destroy()
        except Exception as exc:
            messagebox.showerror("Jarvis", f"Не удалось сохранить: {exc}")

    def _on_cancel():
        root.destroy()

    ttk.Button(btns, text="Проверить ключ", command=_on_test).grid(row=0, column=0, padx=(0, 6))
    ttk.Button(btns, text="Сохранить", command=_on_save).grid(row=0, column=1, padx=6)
    ttk.Button(btns, text="Отмена", command=_on_cancel).grid(row=0, column=2, padx=6)

    main.columnconfigure(1, weight=1)

    root.mainloop()
    return result
