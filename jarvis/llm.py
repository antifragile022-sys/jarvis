"""Gemini-клиент на новом SDK google-genai (с автоматическим function calling)."""
from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any

from .logger import get_logger

log = get_logger("llm")

SYSTEM_PROMPT = (
    "Ты — Джарвис, голосовой ассистент по образу Marvel/Tony Stark, на русском языке. "
    "Отвечай очень кратко, 1-2 предложения, по делу, без markdown и эмодзи "
    "(твой ответ будет прочитан вслух). "
    "Можешь обращаться «сэр». "
    "Если пользователь просит выполнить действие на компьютере — вызывай доступные функции. "
    "Если функции нет, действуй через run_shell или run_python, но осознанно. "
    "Никогда не выдумывай: если не знаешь, скажи об этом."
)

# Признак ошибки «квота закончилась».
_QUOTA_HINTS = (
    "resource_exhausted",
    "quota",
    "429",
    "rate limit",
    "ratelimit",
    "exceeded",
)


class QuotaExceeded(RuntimeError):
    """Бросается, когда Gemini вернул RESOURCE_EXHAUSTED / 429."""


def _looks_like_quota(exc: BaseException) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    return any(h in text for h in _QUOTA_HINTS)


def _strip_markup(text: str) -> str:
    # markdown→plain, эмодзи и спецсимволы убираем, чтобы TTS не зачитывал «звёздочка».
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*|__|\*|_|#+\s*|>\s*|~~", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class GeminiClient:
    """Клиент Gemini с поддержкой автоматического function calling.

    - Если api_key пуст — `available` = False, `ask` возвращает пустую строку.
    - Если квота закончилась — бросает QuotaExceeded (вызывающий код покажет настройки).
    - Если включён agent_mode — передаёт список Python-функций как инструменты,
      SDK сам гоняет цикл tool-call → response.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash-lite",
        fallback_model: str = "gemini-2.5-flash",
        tools: list[Any] | None = None,
        cache_size: int = 64,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._primary = model
        self._fallback = fallback_model
        self._tools = list(tools or [])
        self._client = None
        self._chat = None
        self._types = None
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._cache_size = cache_size
        self._current_model = model
        if self._api_key:
            self._init()

    @property
    def available(self) -> bool:
        return self._chat is not None

    @property
    def model(self) -> str:
        return self._current_model

    def _init(self) -> None:
        try:
            from google import genai  # type: ignore
            from google.genai import types  # type: ignore
        except ImportError:
            log.error("Пакет google-genai не установлен; LLM отключён.")
            return

        try:
            self._client = genai.Client(api_key=self._api_key)
            self._types = types
            self._open_chat(self._primary)
            self._current_model = self._primary
        except Exception as exc:  # pragma: no cover
            log.error("Не удалось инициализировать Gemini: %s", exc)
            self._client = None
            self._chat = None

    def _open_chat(self, model: str) -> None:
        assert self._client is not None and self._types is not None
        types = self._types
        cfg_kwargs: dict[str, Any] = {"system_instruction": SYSTEM_PROMPT}
        if self._tools:
            # «Automatic Function Calling» — передаём список Python-функций.
            cfg_kwargs["tools"] = self._tools
        config = types.GenerateContentConfig(**cfg_kwargs)
        self._chat = self._client.chats.create(model=model, config=config)
        self._current_model = model
        log.info("Gemini chat открыт: model=%s, tools=%d", model, len(self._tools))

    # ---------------- public API ----------------

    def ask(self, prompt: str) -> str:
        """Отправляет prompt, возвращает текст ответа. Бросает QuotaExceeded при лимите."""
        prompt = (prompt or "").strip()
        if not prompt or not self._chat:
            return ""

        # Простейший LRU-кэш для одинаковых вопросов (экономия квоты).
        cached = self._cache.get(prompt)
        if cached is not None:
            self._cache.move_to_end(prompt)
            log.debug("cache hit: %s", prompt[:60])
            return cached

        try:
            response = self._chat.send_message(prompt)
        except Exception as exc:
            if _looks_like_quota(exc):
                log.warning("Gemini: квота исчерпана (%s)", exc)
                raise QuotaExceeded(str(exc)) from exc
            # Однократно пробуем фолбэк-модель, если основная отказала.
            if self._current_model == self._primary and self._fallback and self._fallback != self._primary:
                log.warning("Ошибка %s; пробую fallback-модель %s", exc, self._fallback)
                try:
                    self._open_chat(self._fallback)
                    response = self._chat.send_message(prompt)
                except Exception as exc2:
                    if _looks_like_quota(exc2):
                        raise QuotaExceeded(str(exc2)) from exc2
                    log.error("Gemini fallback тоже не сработал: %s", exc2)
                    return "Извини, сэр, Gemini не отвечает."
            else:
                log.error("Gemini ошибка: %s", exc)
                return "Извини, сэр, Gemini не отвечает."

        text = _strip_markup(getattr(response, "text", "") or "")

        # Обновляем кэш.
        self._cache[prompt] = text
        self._cache.move_to_end(prompt)
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return text

    def reset(self) -> None:
        """Сбрасывает историю диалога (экономия токенов на длинных сессиях)."""
        if self._client is not None:
            self._open_chat(self._current_model)
        self._cache.clear()
