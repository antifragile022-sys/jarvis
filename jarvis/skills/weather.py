"""Погода через бесплатный API Open-Meteo (без ключа)."""
from __future__ import annotations

from ..config import Config
from ..logger import get_logger
from ..router import Intent, compile_patterns

log = get_logger("skills.weather")

WEATHER_CODES_RU: dict[int, str] = {
    0: "ясно",
    1: "преимущественно ясно",
    2: "переменная облачность",
    3: "пасмурно",
    45: "туман",
    48: "изморозь",
    51: "лёгкая морось",
    53: "морось",
    55: "сильная морось",
    61: "небольшой дождь",
    63: "дождь",
    65: "сильный дождь",
    71: "небольшой снег",
    73: "снег",
    75: "сильный снег",
    77: "снежные зёрна",
    80: "ливень",
    81: "сильный ливень",
    82: "очень сильный ливень",
    85: "снегопад",
    86: "сильный снегопад",
    95: "гроза",
    96: "гроза с градом",
    99: "сильная гроза с градом",
}


def _geocode(city: str) -> tuple[float, float, str] | None:
    try:
        import requests
    except ImportError:
        return None
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "ru", "format": "json"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("results") or []
        if not results:
            return None
        first = results[0]
        return float(first["latitude"]), float(first["longitude"]), first.get("name", city)
    except Exception as exc:  # pragma: no cover
        log.error("geocode failed: %s", exc)
        return None


def _fetch_weather(lat: float, lon: float) -> dict | None:
    try:
        import requests
    except ImportError:
        return None
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                "timezone": "auto",
            },
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("current")
    except Exception as exc:  # pragma: no cover
        log.error("weather fetch failed: %s", exc)
        return None


def _format(city: str, current: dict) -> str:
    temp = current.get("temperature_2m")
    code = int(current.get("weather_code") or 0)
    wind = current.get("wind_speed_10m")
    humidity = current.get("relative_humidity_2m")
    desc = WEATHER_CODES_RU.get(code, "неопределённая погода")

    parts = [f"В городе {city}: {desc}"]
    if temp is not None:
        parts.append(f"температура {temp:.0f} градусов")
    if wind is not None:
        parts.append(f"ветер {wind:.0f} километров в час")
    if humidity is not None:
        parts.append(f"влажность {humidity:.0f} процентов")
    return ", ".join(parts) + "."


def _make_handler(config: Config):
    def _weather(m, _t):
        city = (m.groupdict().get("city") or "").strip() or config.default_city
        geo = _geocode(city)
        if not geo:
            return f"Не нашёл город «{city}»."
        lat, lon, resolved = geo
        current = _fetch_weather(lat, lon)
        if not current:
            return "Не удалось получить погоду."
        return _format(resolved, current)

    return _weather


def intents(config: Config) -> list[Intent]:
    handler = _make_handler(config)
    return [
        Intent(
            name="weather_city",
            patterns=compile_patterns([
                r"\bпогода\s+(?:в|во)\s+(?P<city>[\w\-\s]+?)\s*$",
                r"\bкакая\s+погода\s+(?:в|во)\s+(?P<city>[\w\-\s]+?)\s*$",
            ]),
            handler=handler,
            priority=30,
        ),
        Intent(
            name="weather_here",
            patterns=compile_patterns([
                r"\b(?:какая\s+)?погода\s*(?:на улице|сейчас)?\s*$",
            ]),
            handler=handler,
            priority=25,
        ),
    ]
