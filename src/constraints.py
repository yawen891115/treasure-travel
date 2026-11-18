"""Opening hours, travel time and cost helpers (used by the re-ranker, agent and validator)."""

import json
import math
import re

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_TIME = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*$", re.IGNORECASE)


def _to_minutes(text, default_suffix=None):
    """'10:30AM' -> 630. Returns (minutes, suffix_found)."""
    m = _TIME.match(text)
    if not m:
        raise ValueError(f"cannot read time: {text!r}")
    hour, minute = int(m.group(1)), int(m.group(2) or 0)
    suffix = (m.group(3) or default_suffix or "").lower()
    if suffix == "pm" and hour != 12:
        hour += 12
    if suffix == "am" and hour == 12:
        hour = 0
    return hour * 60 + minute, m.group(3) is not None


def parse_range(text):
    """'11AM–2PM' -> (660, 840). Handles '5–10PM', overnight '8PM–2AM' (end > 1440)."""
    start_txt, end_txt = re.split(r"\s*(?:–|-|to)\s*", text.strip(), maxsplit=1)
    end, _ = _to_minutes(end_txt)
    end_suffix = (
        "pm"
        if re.search(r"pm", end_txt, re.I)
        else ("am" if re.search(r"am", end_txt, re.I) else None)
    )
    start, had_suffix = _to_minutes(start_txt, default_suffix=end_suffix)
    if not had_suffix and start > end:  # '11–2PM' means 11AM, not 11PM
        start, _ = _to_minutes(start_txt, default_suffix="am")
    if end <= start:  # closes after midnight
        end += 24 * 60
    return start, end


def parse_hours(hours):
    """Google Local hours -> {0: [(open, close), ...], ..., 6: [...]} with 0 = Monday.

    Accepts the raw list [["Monday", "9AM–5PM"], ...] or its JSON text. Unknown -> {}.
    """
    if isinstance(hours, str):
        hours = json.loads(hours) if hours.strip().startswith("[") else []
    result = {}
    for day, text in hours or []:
        day = str(day).strip().lower()
        if day not in DAYS:
            continue
        idx, text = DAYS.index(day), str(text).strip()
        low = text.lower()
        if low == "closed":
            result[idx] = []
        elif "24 hours" in low:
            result[idx] = [(0, 24 * 60)]
        else:
            try:
                result[idx] = [parse_range(part) for part in text.split(",") if part.strip()]
            except ValueError:
                continue  # leave this day unknown
    return result


def is_open(parsed, weekday, start_min, end_min):
    """True/False if we know, None if the hours for that day are unknown."""
    prev = parsed.get((weekday - 1) % 7, [])
    carried = [(a - 1440, b - 1440) for a, b in prev if b > 1440]  # last night's late hours
    if any(a <= start_min and end_min <= b for a, b in carried):
        return True
    if weekday not in parsed:
        return None
    return any(a <= start_min and end_min <= b for a, b in parsed[weekday])


def haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def estimate_travel_minutes(lat1, lng1, lat2, lng2, mode="walk"):
    """Offline estimate: straight-line distance x 1.3 (roads are not straight) / typical speed."""
    km = haversine_km(lat1, lng1, lat2, lng2) * 1.3
    if mode == "drive":
        return round(km / 35.0 * 60 + 5)  # + 5 min to park
    return round(km / 4.8 * 60)


_FOOD = (
    "restaurant",
    "cafe",
    "coffee",
    "bakery",
    "pizza",
    "seafood",
    "bar",
    "brewery",
    "winery",
    "ice cream",
    "dessert",
)
_FREE = (
    "park",
    "beach",
    "garden",
    "landmark",
    "monument",
    "historical",
    "hiking",
    "scenic",
    "lighthouse",
    "library",
)


def estimate_cost(price, categories):
    """Rough cost per person in USD from Google's '$'..'$$$$' price level and the categories."""
    cats = str(categories).lower()
    level = len(price) if isinstance(price, str) and set(price) == {"$"} else 0
    if any(re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", cats) for w in _FOOD):
        return {0: 18, 1: 12, 2: 25, 3: 50, 4: 90}[min(level, 4)]
    if any(re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", cats) for w in _FREE):
        return 0
    if "museum" in cats or "gallery" in cats or "zoo" in cats or "aquarium" in cats:
        return 20
    return {0: 15, 1: 10, 2: 20, 3: 40, 4: 70}[min(level, 4)]


def hhmm_to_min(text):
    value = str(text).strip()
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d|24:00", value):
        raise ValueError("time must be HH:MM between 00:00 and 24:00")
    h, m = value.split(":")
    return int(h) * 60 + int(m)


def min_to_hhmm(minutes):
    return f"{int(minutes) // 60:02d}:{int(minutes) % 60:02d}"
