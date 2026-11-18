"""The tools the LLM can call, described in JSON Schema, plus the Python code that runs them."""

import json
import math

from agent.maps import hours_text
from src.constraints import DAYS, estimate_cost, hhmm_to_min

SEARCH = {
    "name": "search_places",
    "description": "Find places that match interests (e.g. 'art museum', 'coffee', 'seafood'). "
    "Optionally only places within max_minutes of near_place_id (or of the trip start).",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to look for, in a few words."},
            "near_place_id": {
                "type": "string",
                "description": "Search around this place. Omit = trip start.",
            },
            "max_minutes": {
                "type": "integer",
                "description": "Max travel minutes from that point.",
            },
            "k": {"type": "integer", "description": "How many results (default 6)."},
        },
        "required": ["query"],
    },
}
HOURS = {
    "name": "get_opening_hours",
    "description": "Opening hours of a place on a weekday (e.g. 'Saturday'). "
    "Always check before scheduling.",
    "input_schema": {
        "type": "object",
        "properties": {"place_id": {"type": "string"}, "day": {"type": "string"}},
        "required": ["place_id", "day"],
    },
}
TRAVEL = {
    "name": "get_travel_time",
    "description": "Travel time in minutes between two places. "
    "Use 'start' for the trip's starting point.",
    "input_schema": {
        "type": "object",
        "properties": {
            "from_place_id": {"type": "string"},
            "to_place_id": {"type": "string"},
            "mode": {"type": "string", "enum": ["walk", "drive"]},
        },
        "required": ["from_place_id", "to_place_id"],
    },
}
BUDGET = {
    "name": "check_budget",
    "description": "Estimated total cost for the whole group to visit these places, "
    "compared with the budget.",
    "input_schema": {
        "type": "object",
        "properties": {"place_ids": {"type": "array", "items": {"type": "string"}}},
        "required": ["place_ids"],
    },
}
PREFS = {
    "name": "update_trip_preferences",
    "description": "Save what you learned about the trip so later turns remember it: "
    "group_size, date (YYYY-MM-DD, required for live maps), day, start, "
    "end, budget, interests, mode, max_leg_minutes, members (each member's interests).",
    "input_schema": {
        "type": "object",
        "properties": {"preferences": {"type": "object"}},
        "required": ["preferences"],
    },
}
SUBMIT = {
    "name": "submit_itinerary",
    "description": "Submit the final plan. Times are 24-hour 'HH:MM'. "
    "Call this exactly once, at the end.",
    "input_schema": {
        "type": "object",
        "properties": {
            "stops": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "place_id": {"type": "string"},
                        "name": {"type": "string"},
                        "arrive": {"type": "string"},
                        "leave": {"type": "string"},
                    },
                    "required": ["place_id", "arrive", "leave"],
                },
            },
            "summary": {
                "type": "string",
                "description": "2-3 friendly sentences for the traveler.",
            },
        },
        "required": ["stops", "summary"],
    },
}
ALL_TOOLS = [SEARCH, HOURS, TRAVEL, BUDGET, PREFS, SUBMIT]


class ToolBox:
    """Runs tool calls for one trip. `request` holds the trip's facts (start, day, budget...)."""

    def __init__(self, index, maps, request=None, preferences=None):
        self.index, self.maps = index, maps
        self.preferences = dict(preferences or {})
        self.request = {**self.preferences, **(request or {})}
        if hasattr(maps, "for_request"):
            self.maps = maps.for_request(self.request)
        self.submitted = None
        self.calls = []

    def _loc(self, place_id):
        if place_id in (None, "", "start"):
            o = self.request.get("origin")
            return (o["lat"], o["lng"]) if o else None
        row = self.index.places.iloc[self.index.by_id[place_id]]
        return float(row["lat"]), float(row["lng"])

    def run(self, name, args):
        self.calls.append(name)
        if name not in {tool["name"] for tool in ALL_TOOLS}:
            return {"error": "unknown tool"}
        if not isinstance(args, dict):
            return {"error": "tool arguments must be an object"}
        try:
            return getattr(self, "_" + name)(**args)
        except KeyError as e:
            return {"error": f"unknown id {e}"}
        except Exception as e:  # return errors to the model so it can try again
            return {"error": f"{type(e).__name__}: {e}"}

    def _search_places(self, query, near_place_id=None, max_minutes=None, k=6):
        near = self._loc(near_place_id)
        limit = max_minutes if max_minutes is not None else self.request.get("max_leg_minutes")
        mode = self.request.get("mode", "walk")
        return {
            "places": self.index.search(
                query,
                near=near,
                max_minutes=limit if near else None,
                mode=mode,
                k=max(1, min(int(k), 10)),
            )
        }

    def _get_opening_hours(self, place_id, day):
        weekday = DAYS.index(str(day).strip().lower())
        return {
            "place_id": place_id,
            "day": day.title(),
            "hours": hours_text(self.maps.opening_hours(place_id, weekday)),
        }

    def _get_travel_time(self, from_place_id, to_place_id, mode=None):
        mode = mode or self.request.get("mode", "walk")
        return {
            "minutes": self.maps.travel_minutes(
                self._loc(from_place_id), self._loc(to_place_id), mode
            ),
            "mode": mode,
        }

    def _check_budget(self, place_ids):
        group = int(self.request.get("group_size") or self.preferences.get("group_size") or 1)
        per = []
        for pid in place_ids:
            row = self.index.places.iloc[self.index.by_id[pid]]
            per.append(
                {"place_id": pid, "cost_per_person": estimate_cost(row["price"], row["categories"])}
            )
        total = sum(p["cost_per_person"] for p in per) * group
        budget = self.request.get("budget")
        return {
            "group_size": group,
            "total": total,
            "budget": budget,
            "places": per,
            "within_budget": None if budget is None else total <= float(budget),
        }

    def _update_trip_preferences(self, preferences):
        if not isinstance(preferences, dict):
            raise ValueError("preferences must be an object")
        allowed = {
            "group_size",
            "date",
            "day",
            "start",
            "end",
            "budget",
            "interests",
            "mode",
            "max_leg_minutes",
            "members",
            "origin",
        }
        updates = {k: v for k, v in preferences.items() if k in allowed}
        for key in ("start", "end"):
            if key in updates:
                hhmm_to_min(updates[key])
        for key in ("group_size", "max_leg_minutes", "budget"):
            if key in updates:
                if isinstance(updates[key], bool) or not isinstance(updates[key], (int, float)):
                    raise ValueError(f"{key} must be numeric")
                if not math.isfinite(updates[key]):
                    raise ValueError(f"{key} must be finite")
                if key == "group_size" and not float(updates[key]).is_integer():
                    raise ValueError("group_size must be a whole number")
                if updates[key] < 0 or (key == "group_size" and updates[key] < 1):
                    raise ValueError(f"invalid {key}")
        if "mode" in updates and updates["mode"] not in ("walk", "drive"):
            raise ValueError("mode must be walk or drive")
        if "day" in updates:
            updates["weekday"] = DAYS.index(str(updates["day"]).lower())
        if "date" in updates:
            from datetime import date
            trip_date = date.fromisoformat(updates["date"])
            updates["weekday"] = trip_date.weekday()
            updates["day"] = DAYS[trip_date.weekday()]
        self.preferences.update(updates)
        self.request.update(updates)
        if getattr(self.maps, "name", None) == "google":
            self.maps.trip_date = self.request.get("date")
        return {"saved": self.preferences}

    def _submit_itinerary(self, stops, summary=""):
        if not isinstance(stops, list) or not stops:
            return {"error": "provide at least one stop"}
        for s in stops:
            hhmm_to_min(s["arrive"]), hhmm_to_min(s["leave"])  # raises if the format is wrong
            if s["place_id"] not in self.index.by_id:
                return {"error": f"unknown place_id {s['place_id']}; use ids from search results"}
            s.setdefault("name", self.index.places["name"].iat[self.index.by_id[s["place_id"]]])
        if getattr(self.maps, "name", None) == "google":
            from agent.validator import validate
            problems = validate({"stops": stops}, self.request, self.index, self.maps)
            if problems:
                return {"error": "live validation failed", "problems": problems}
        self.submitted = {"stops": stops, "summary": summary}
        return {"accepted": True}


def tool_result_text(result):
    return json.dumps(result, ensure_ascii=False)
