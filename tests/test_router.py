from jarvis.config import Config
from jarvis.skills import build_default_router


def _router():
    return build_default_router(Config())


def test_time_intent_matches():
    r = _router()
    matched = r.match("сколько времени")
    assert matched is not None
    assert matched[0].name == "time"


def test_date_intent_matches():
    r = _router()
    matched = r.match("какое сегодня число")
    assert matched is not None
    assert matched[0].name == "date"


def test_volume_set_extracts_number():
    r = _router()
    matched = r.match("громкость 50")
    assert matched is not None
    assert matched[0].name == "volume_set"
    assert matched[1].group("pct") == "50"


def test_volume_up_matches():
    r = _router()
    assert r.match("сделай громче")[0].name == "volume_up"
    assert r.match("прибавь звук")[0].name == "volume_up"


def test_volume_down_matches():
    r = _router()
    assert r.match("сделай потише")[0].name == "volume_down"


def test_mute_unmute_match():
    r = _router()
    assert r.match("выключи звук")[0].name == "mute"
    assert r.match("включи звук")[0].name == "unmute"


def test_brightness_set_extracts_number():
    r = _router()
    matched = r.match("яркость 80")
    assert matched is not None
    assert matched[0].name == "brightness_set"
    assert matched[1].group("pct") == "80"


def test_screenshot_matches():
    r = _router()
    assert r.match("сделай скриншот")[0].name == "screenshot"
    assert r.match("снимок экрана")[0].name == "screenshot"


def test_lock_matches():
    r = _router()
    assert r.match("заблокируй компьютер")[0].name == "lock"


def test_reboot_matches():
    r = _router()
    assert r.match("перезагрузи компьютер")[0].name == "reboot"


def test_google_search_extracts_query():
    r = _router()
    matched = r.match("загугли как варить борщ")
    assert matched is not None
    assert matched[0].name == "google_search"
    assert matched[1].group("q") == "как варить борщ"


def test_youtube_search_extracts_query():
    r = _router()
    matched = r.match("найди на ютубе AC/DC")
    assert matched is not None
    assert matched[0].name == "youtube_search"
    assert "AC/DC".lower() in matched[1].group("q")


def test_open_site_matches():
    r = _router()
    matched = r.match("открой ютуб")
    assert matched is not None
    assert matched[0].name == "open_site"
    assert matched[1].group("site").strip() == "ютуб"


def test_weather_with_city():
    r = _router()
    matched = r.match("погода в париже")
    assert matched is not None
    assert matched[0].name == "weather_city"
    assert matched[1].group("city").strip() == "париже"


def test_weather_without_city():
    r = _router()
    matched = r.match("какая погода")
    assert matched is not None
    assert matched[0].name in ("weather_here", "weather_city")


def test_cpu_matches():
    r = _router()
    assert r.match("загрузка процессора")[0].name == "cpu"


def test_battery_matches():
    r = _router()
    assert r.match("сколько заряда")[0].name == "battery"


def test_hello_matches():
    r = _router()
    assert r.match("привет")[0].name == "hello"


def test_who_are_you_matches():
    r = _router()
    assert r.match("кто ты")[0].name == "who_are_you"


def test_unknown_returns_none():
    r = _router()
    assert r.match("расскажи мне про чёрные дыры") is None
