"""Opening hours and travel times, from two interchangeable sources.

OfflineMaps  - uses the hours stored in the dataset + a distance-based travel estimate.
               Free, fast, used for the 200-request evaluation.
GoogleMaps   - calls Google Places API (New) and Routes API for live data
               (needs GOOGLE_MAPS_API_KEY).
               Requires verified Place ID mappings and an explicit upcoming trip date.
               Content is not persisted; there is no silent offline fallback.
"""

import json
import os
import math

import requests

from pathlib import Path
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
import re
from src.constraints import estimate_travel_minutes, min_to_hhmm


def hours_text(intervals):
    if intervals is None:
        return "unknown"
    if not intervals:
        return "Closed"
    return ", ".join(f"{min_to_hhmm(a)}-{min_to_hhmm(b % 1440)}" for a, b in intervals)


class OfflineMaps:
    name = "offline"

    def __init__(self, index):
        self.index = index

    def opening_hours(self, place_id, weekday):
        """List of (open_min, close_min) for that weekday, [] if closed, None if unknown."""
        item = self.index.by_id[place_id]
        return self.index.hours[item].get(weekday)

    def travel_minutes(self, a, b, mode="walk"):
        """a and b are (lat, lng) pairs."""
        return estimate_travel_minutes(a[0], a[1], b[0], b[1], mode)


class GoogleMaps(OfflineMaps):
    """Request-scoped live checks. No Google content is persisted or reused across turns.

    Catalog identity is manually verified using GOOGLE_PLACE_IDS_FILE; do not guess
    a business from the first fuzzy search result. Costs remain local estimates.
    """
    name = "google"
    PLACES = "https://places.googleapis.com/v1"
    ROUTES = "https://routes.googleapis.com/directions/v2:computeRoutes"

    def __init__(self, index, api_key=None, place_ids=None, trip_date=None, session=None):
        super().__init__(index)
        self.key = api_key or os.environ["GOOGLE_MAPS_API_KEY"]
        if not self.key:
            raise ValueError("Google API key is required")
        if place_ids is None:
            path = os.environ.get("GOOGLE_PLACE_IDS_FILE")
            place_ids = json.loads(Path(path).read_text()) if path else {}
        if not isinstance(place_ids, dict):
            raise ValueError("Google place mappings must be an object")
        self.place_ids = place_ids
        self.trip_date = trip_date
        self.session = session or requests.Session()
        self.calls = 0
        self.max_calls = 40

    def for_request(self, request):
        return GoogleMaps(self.index, self.key, self.place_ids, request.get("date"))

    def _date(self):
        try:
            day = date.fromisoformat(self.trip_date)
        except (TypeError, ValueError):
            raise ValueError("Live checks require an explicit YYYY-MM-DD trip date") from None
        today = datetime.now(ZoneInfo("America/New_York")).date()
        if not today <= day <= today + timedelta(days=6):
            raise ValueError("Live Boston hours are supported only for today and next six days")
        return day

    def _call(self, method, url, fields, body=None):
        if self.calls >= self.max_calls:
            raise ValueError("Per-turn Google request limit reached")
        self.calls += 1
        try:
            response = self.session.request(method, url, timeout=(3, 10),
                headers={"X-Goog-Api-Key": self.key, "X-Goog-FieldMask": fields},
                json=body, allow_redirects=False)
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError("unexpected status")
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("unexpected response")
            return payload
        except (requests.RequestException, ValueError):
            raise ValueError("Live map provider unavailable; feasibility is unknown") from None

    def opening_hours(self, place_id, weekday):
        target = self._date()
        # Validator asks previous day for overnight hours; intervals below already
        # include carry-over clipped to target date, so no previous-day lookup needed.
        if weekday == (target.weekday() - 1) % 7:
            return []
        if weekday != target.weekday():
            raise ValueError("Weekday does not match explicit trip date")
        gid = self.place_ids.get(place_id)
        if not isinstance(gid, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", gid):
            return None
        payload = self._call("GET", f"{self.PLACES}/places/{gid}",
            "currentOpeningHours,businessStatus")
        if payload.get("businessStatus") != "OPERATIONAL":
            return None
        hours = payload.get("currentOpeningHours")
        if not hours or "periods" not in hours:
            return None
        midnight = datetime.combine(target, time.min)
        intervals = []
        for period in hours["periods"]:
            opening, closing = period.get("open", {}), period.get("close")
            if closing is None:
                if (opening.get("day") == 0 and opening.get("hour", 0) == 0
                        and opening.get("minute", 0) == 0):
                    return [(0, 1440)]
                return None
            def endpoint(value):
                d = value.get("date", {})
                return datetime(d["year"], d["month"], d["day"],
                                value.get("hour", 0), value.get("minute", 0))
            try:
                a = max(0, int((endpoint(opening) - midnight).total_seconds() / 60))
                b = min(1440, int((endpoint(closing) - midnight).total_seconds() / 60))
            except (KeyError, ValueError, TypeError):
                return None
            if b > a:
                intervals.append((a, b))
        return sorted(intervals)

    def travel_minutes(self, a, b, mode="walk"):
        self._date()
        if mode not in ("walk", "drive"):
            raise ValueError("mode must be walk or drive")
        for loc in (a, b):
            if (not loc or len(loc) != 2 or not all(math.isfinite(x) for x in loc)
                    or not -90 <= loc[0] <= 90 or not -180 <= loc[1] <= 180):
                raise ValueError("Invalid route coordinates")
        body = {
            "origin": {"location": {"latLng": {"latitude": a[0], "longitude": a[1]}}},
            "destination": {"location": {"latLng": {"latitude": b[0], "longitude": b[1]}}},
            "travelMode": "WALK" if mode == "walk" else "DRIVE",
        }
        payload = self._call("POST", self.ROUTES, "routes.duration", body)
        routes = payload.get("routes", [])
        try:
            duration = routes[0]["duration"]
            if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?s", duration):
                raise ValueError()
            return math.ceil(float(duration[:-1]) / 60)
        except (KeyError, IndexError, TypeError, ValueError):
            raise ValueError("Google returned no valid route; feasibility is unknown") from None


def make_maps(index):
    """MAPS_MODE=google uses live Google data; anything else uses the free offline version."""
    mode = os.environ.get("MAPS_MODE", "offline")
    if mode == "google":
        if not os.environ.get("GOOGLE_MAPS_API_KEY"):
            raise ValueError("MAPS_MODE=google requires GOOGLE_MAPS_API_KEY")
        return GoogleMaps(index)
    if mode != "offline":
        raise ValueError("MAPS_MODE must be offline or google")
    return OfflineMaps(index)
