from src.constraints import estimate_cost, is_open, parse_hours, parse_range


def test_parse_range_variants():
    assert parse_range("10AM–6PM") == (600, 1080)
    assert parse_range("10:30AM–6:30PM") == (630, 1110)
    assert parse_range("5–10PM") == (1020, 1320)  # start inherits PM
    assert parse_range("11–2PM") == (660, 840)  # ...unless that would be after the end
    assert parse_range("8PM–2AM") == (1200, 1560)  # closes after midnight
    assert parse_range("12PM–12AM") == (720, 1440)


def test_parse_hours_and_is_open():
    hours = [
        ["Monday", "Closed"],
        ["Tuesday", "11AM–2PM, 5–9PM"],
        ["Wednesday", "Open 24 hours"],
        ["Friday", "8PM–2AM"],
    ]
    h = parse_hours(hours)
    assert h[0] == [] and is_open(h, 0, 600, 660) is False
    assert is_open(h, 1, 690, 780) is True  # 11:30-13:00 inside lunch
    assert is_open(h, 1, 900, 960) is False  # 15:00-16:00 between lunch and dinner
    assert is_open(h, 2, 0, 1440) is True
    assert is_open(h, 5, 30, 60) is True  # Saturday 00:30 = Friday night's hours
    assert is_open(h, 3, 600, 660) is None  # Thursday unknown


def test_estimate_cost():
    assert estimate_cost("$$", "Seafood restaurant, Restaurant") == 25
    assert estimate_cost("", "Park") == 0
    assert estimate_cost(None, "Art museum, Museum") == 20
