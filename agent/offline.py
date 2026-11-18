"""Deterministic, no-key itinerary planning. This is not an LLM or live Maps service.

Only explicit structured fields or a small documented text grammar are interpreted.
Missing origin/budget/time constraints are requested, never fabricated. Default visit
length is 60 minutes and default requested stop count is 3; both are disclosed.
"""

import math
import re

from agent.validator import validate
from src.constraints import DAYS, estimate_cost, hhmm_to_min, min_to_hhmm


def parse_preferences(text):
    """Read simple explicit English fields; do not pretend to understand arbitrary prose."""
    out = {}
    low = text.lower()
    for day in DAYS:
        if re.search(rf"\b{day}\b", low):
            out.update(day=day.title(), weekday=DAYS.index(day))
            break
    span = re.search(r"\b(\d{1,2}:\d{2})\s*(?:-|–|to)\s*(\d{1,2}:\d{2})\b", low)
    if span:
        out.update(start=span[1].zfill(5), end=span[2].zfill(5))
    else:
        for field, prefix in [
            ("start", r"(?:from|start(?:ing)?(?: at)?)"),
            ("end", r"(?:until|end(?:ing)?(?: at)?)"),
        ]:
            match = re.search(rf"\b{prefix}\s+(\d{{1,2}}:\d{{2}})\b", low)
            if match:
                out[field] = match[1].zfill(5)
    for field, pattern, cast in [
        ("group_size", r"\b(\d+)\s+(?:people|persons|travelers)\b", int),
        ("budget", r"(?:\$|budget\s*(?:is|of|=|:)?\s*)(\d+(?:\.\d+)?)", float),
        (
            "max_leg_minutes",
            r"(?:max(?:imum)?(?: leg)?|limit)\s*(?:=|:)?\s*(\d+)\s*(?:min|minutes)\b",
            int,
        ),
        ("n_stops", r"\b(\d+)\s+stops\b", int),
        ("visit_minutes", r"\b(\d+)\s*(?:min|minutes)\s*(?:per stop|each stop)\b", int),
    ]:
        match = re.search(pattern, low)
        if match:
            out[field] = cast(match[1])
    if re.search(r"\b(?:walking|walk)\b", low):
        out["mode"] = "walk"
    elif re.search(r"\b(?:driving|drive)\b", low):
        out["mode"] = "drive"
    origin = re.search(
        r"\borigin\s*(?:=|:)?\s*\(?\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)", low
    )
    if origin:
        out["origin"] = {"lat": float(origin[1]), "lng": float(origin[2])}
    interests = re.search(r"\b(?:interests?|query)\s*[:=]\s*(.+?)(?:;|$)", text, re.I)
    if interests:
        out["query"] = interests[1].strip()
    if "budget" in out and re.search(r"per person|each person", low):
        # The planner requires a total group budget rather than guessing a conversion.
        out["budget"] = None
    return out


def request_errors(prefs):
    errors = []
    for key in [
        "origin",
        "budget",
        "group_size",
        "start",
        "end",
        "weekday",
        "mode",
        "max_leg_minutes",
    ]:
        if key not in prefs or prefs[key] is None:
            errors.append(key)
    if errors:
        return errors
    try:
        if not (0 <= int(prefs["weekday"]) <= 6) or prefs["mode"] not in {"walk", "drive"}:
            errors.append("weekday/mode")
        if hhmm_to_min(prefs["start"]) >= hhmm_to_min(prefs["end"]):
            errors.append("start/end (same-day increasing time range)")
        lat, lng = float(prefs["origin"]["lat"]), float(prefs["origin"]["lng"])
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            errors.append("origin coordinates")
        for key in ["budget", "group_size", "max_leg_minutes", "n_stops", "visit_minutes"]:
            raw = prefs.get(key, {"n_stops": 3, "visit_minutes": 60}.get(key))
            if isinstance(raw, bool):
                errors.append(key)
            value = float(raw)
            if not math.isfinite(value) or value < (0 if key == "budget" else 1):
                errors.append(key)
            if key in {"group_size", "n_stops", "visit_minutes"} and not value.is_integer():
                errors.append(key)
        if float(prefs.get("n_stops", 3)) > 20:
            errors.append("n_stops (maximum 20)")
    except (KeyError, TypeError, ValueError):
        errors.append("invalid trip fields")
    return errors


class OfflinePlanner:
    """Greedy ranked-candidate planner with conservative hard-constraint checks."""

    def __init__(self, index, maps):
        self.index, self.maps = index, maps

    def run(self, user_text, request=None, history=None, preferences=None, candidates=None):
        prefs = dict(preferences or {})
        prefs.update(request or {})
        if request and "weekday" in request and "day" not in request:
            prefs.pop("day", None)
        prefs.update(parse_preferences(user_text))
        if "day" in prefs and str(prefs["day"]).lower() in DAYS:
            prefs["weekday"] = DAYS.index(str(prefs["day"]).lower())
        query = prefs.get("query") or prefs.get("interests") or user_text
        if isinstance(query, list):
            query = " ".join(str(value) for value in query)
        prefs["query"] = str(query)
        errors = request_errors(prefs)
        itinerary = None
        if errors:
            reply = (
                "Offline planner (not an LLM): please provide or correct "
                + ", ".join(errors)
                + ". Example: Saturday 10:00-18:00, 2 people, budget $100, walk, "
                "max 20 minutes, origin (42.3601, -71.0589), interests: art and coffee. "
                "Coordinates are required; place names are not geocoded."
            )
        else:
            for key in ["group_size", "weekday", "n_stops", "visit_minutes"]:
                if key in prefs:
                    prefs[key] = int(prefs[key])
            prefs["budget"] = float(prefs["budget"])
            prefs["max_leg_minutes"] = float(prefs["max_leg_minutes"])
            itinerary = self.plan(prefs, candidates)
            count = len(itinerary["stops"])
            target = int(prefs.get("n_stops", 3))
            reply = (
                f"Offline rule-based plan: {count} of {target} requested stops; "
                f"{int(prefs.get('visit_minutes', 60))} minutes per stop. "
                "Hours come from the selected data source; "
                "costs and travel times may be estimates. "
                "No LLM was used."
            )
            if count < target:
                reply += " Not enough ranked candidates met all supplied constraints."
            itinerary["summary"] = reply
            if not count:
                itinerary = None
        messages = list(history or []) + [
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": reply},
        ]
        return {
            "itinerary": itinerary,
            "reply": reply,
            "preferences": prefs,
            "tool_calls": [],
            "steps": 1,
            "usage": {"input_tokens": 0, "output_tokens": 0},
            "messages": messages,
            "backend": "offline",
            "missing_fields": errors,
        }

    def plan(self, req, candidates=None):
        rows = candidates if candidates is not None else self.index.search(req["query"], k=100)
        seen, stops = set(), []
        now, end = hhmm_to_min(req["start"]), hhmm_to_min(req["end"])
        loc = float(req["origin"]["lat"]), float(req["origin"]["lng"])
        remaining = float(req["budget"])
        day = int(req["weekday"])
        duration = int(req.get("visit_minutes", 60))
        target = int(req.get("n_stops", 3))
        while len(stops) < target:
            selected = None
            for candidate in rows:
                pid = candidate.get("place_id")
                if pid in seen or pid not in self.index.by_id:
                    continue
                row = self.index.places.iloc[self.index.by_id[pid]]
                cost = estimate_cost(row["price"], row["categories"]) * int(req["group_size"])
                next_loc = float(row["lat"]), float(row["lng"])
                travel = self.maps.travel_minutes(loc, next_loc, req["mode"])
                if not math.isfinite(travel) or travel < 0 or travel > req["max_leg_minutes"]:
                    continue
                if cost > remaining:
                    continue
                today = self.maps.opening_hours(pid, day)
                prev = self.maps.opening_hours(pid, (day - 1) % 7) or []
                intervals = list(today or []) + [(a - 1440, b - 1440) for a, b in prev if b > 1440]
                for opening, closing in sorted(intervals):
                    arrival = max(now + math.ceil(travel), opening)
                    if arrival + duration <= min(closing, end):
                        selected = (pid, row["name"], arrival, next_loc, cost)
                        break
                if selected:
                    break
            if selected is None:
                break
            pid, name, arrive, loc, cost = selected
            now = arrive + duration
            stops.append(
                {
                    "place_id": pid,
                    "name": name,
                    "arrive": min_to_hhmm(arrive),
                    "leave": min_to_hhmm(now),
                }
            )
            seen.add(pid)
            remaining -= cost
        result = {"stops": stops, "estimated_total_cost": float(req["budget"]) - remaining}
        # Independent judge is a final defense, never silently return a violating plan.
        if stops and validate(result, req, self.index, self.maps):
            return {"stops": [], "estimated_total_cost": 0}
        return result
