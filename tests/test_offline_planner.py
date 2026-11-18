"""No network/model required: deterministic planning is tested separately from FakeLLM."""

import pandas as pd
import pytest

from agent.offline import OfflinePlanner, parse_preferences
from agent.validator import validate


class StubIndex:
    def __init__(self):
        self.places = pd.DataFrame(
            [
                {
                    "gmap_id": "closed",
                    "name": "Closed",
                    "price": "",
                    "categories": "Museum",
                    "lat": 1,
                    "lng": 1,
                },
                {
                    "gmap_id": "unknown",
                    "name": "Unknown",
                    "price": "",
                    "categories": "Park",
                    "lat": 1,
                    "lng": 1,
                },
                {
                    "gmap_id": "far",
                    "name": "Far",
                    "price": "",
                    "categories": "Park",
                    "lat": 2,
                    "lng": 2,
                },
                {
                    "gmap_id": "museum",
                    "name": "Museum",
                    "price": "",
                    "categories": "Museum",
                    "lat": 1,
                    "lng": 1,
                },
                {
                    "gmap_id": "park",
                    "name": "Park",
                    "price": "",
                    "categories": "Park",
                    "lat": 1,
                    "lng": 1,
                },
            ]
        )
        self.by_id = {p: i for i, p in enumerate(self.places["gmap_id"])}

    def search(self, query, k=100):
        return [{"place_id": p} for p in self.by_id][:k]


class StubMaps:
    def opening_hours(self, pid, day):
        if pid == "unknown":
            return None
        if day != 5 or pid == "closed":
            return []
        return [(600, 1020)]

    def travel_minutes(self, a, b, mode):
        return 90 if b[0] == 2 else 10


REQ = {
    "start": "09:00",
    "end": "18:00",
    "weekday": 5,
    "budget": 50,
    "group_size": 2,
    "max_leg_minutes": 20,
    "mode": "walk",
    "query": "park museum",
    "origin": {"lat": 1, "lng": 1},
}


def test_feasible_plan_waits_for_opening_and_checks_all_constraints():
    idx, maps = StubIndex(), StubMaps()
    result = OfflinePlanner(idx, maps).run("", request=REQ)
    stops = result["itinerary"]["stops"]
    assert [s["place_id"] for s in stops] == ["museum", "park"]
    assert stops[0]["arrive"] == "10:00"
    assert stops[1]["arrive"] == "11:10"
    assert validate(result["itinerary"], REQ, idx, maps) == []
    assert "2 of 3" in result["reply"]
    assert result["usage"]["input_tokens"] == 0


def test_zero_budget_selects_free_stop_only():
    result = OfflinePlanner(StubIndex(), StubMaps()).run("", request={**REQ, "budget": 0})
    assert [s["place_id"] for s in result["itinerary"]["stops"]] == ["park"]


def test_missing_fields_not_invented_and_next_turn_completes():
    planner = OfflinePlanner(StubIndex(), StubMaps())
    out = planner.run("Saturday 09:00-18:00, 2 people, walk, max 20 minutes, interests: parks")
    assert out["itinerary"] is None
    assert "origin" in out["missing_fields"] and "budget" in out["missing_fields"]
    out = planner.run("origin (1, 1), budget $50", preferences=out["preferences"])
    assert out["itinerary"]
    assert out["preferences"]["query"] == "parks"


@pytest.mark.parametrize(
    "changes",
    [
        {"budget": -1},
        {"budget": float("nan")},
        {"group_size": True},
        {"origin": {"lat": 100, "lng": 1}},
        {"start": "19:00"},
        {"weekday": 7},
        {"mode": "plane"},
        {"n_stops": 100},
        {"visit_minutes": 0},
    ],
)
def test_invalid_constraints_return_clear_request_not_plan(changes):
    out = OfflinePlanner(StubIndex(), StubMaps()).run("", request={**REQ, **changes})
    assert out["itinerary"] is None and out["missing_fields"]


def test_per_person_budget_not_misread_as_total():
    assert parse_preferences("budget $50 per person")["budget"] is None


def test_no_feasible_plan_is_not_reported_as_success():
    out = OfflinePlanner(StubIndex(), StubMaps()).run("", request={**REQ, "end": "09:30"})
    assert out["itinerary"] is None
    assert "0 of 3" in out["reply"]


def test_explicit_weekday_overrides_previous_day():
    out = OfflinePlanner(StubIndex(), StubMaps()).run(
        "", request=REQ, preferences={"day": "Monday"}
    )
    assert out["preferences"]["weekday"] == 5
    assert out["itinerary"]
