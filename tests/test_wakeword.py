from jarvis.wakeword import WakeWordDetector


def test_extracts_command_after_wake_word():
    d = WakeWordDetector(["джарвис", "эй джарвис"])
    assert d.detect("джарвис сколько времени") == "сколько времени"
    assert d.detect("Джарвис, сколько времени") == "сколько времени"
    assert d.detect("эй джарвис какая погода") == "какая погода"


def test_returns_empty_when_only_wake_word():
    d = WakeWordDetector(["джарвис"])
    assert d.detect("джарвис") == ""
    assert d.detect("Джарвис!") == ""


def test_returns_none_when_no_wake_word():
    d = WakeWordDetector(["джарвис"])
    assert d.detect("сколько времени") is None
    assert d.detect("") is None


def test_always_active_mode_ignores_wake_word():
    d = WakeWordDetector(["джарвис"], always_active=True)
    assert d.detect("сколько времени") == "сколько времени"
    assert d.detect("джарвис громче") == "джарвис громче"


def test_longer_wake_word_matched_first():
    d = WakeWordDetector(["джарвис", "эй джарвис"])
    # «эй джарвис какая погода» — должно отрезать целиком «эй джарвис».
    assert d.detect("эй джарвис какая погода") == "какая погода"
