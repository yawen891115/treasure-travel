import json

import pandas as pd

from agent.validator import validate
from src.constraints import estimate_travel_minutes, parse_hours


class StubIndex:
    def __init__(self):
        self.places = pd.DataFrame(
            [
                {
                    "gmap_id": "museum",
                    "name": "Museum",
                    "categories": "Art museum",
                    "price": "",
                    "lat": 41.826,
                    "lng": -71.407,
                    "hours": json.dumps([["Saturday", "10AM–5PM"], ["Monday", "Closed"]]),
                },
                {
                    "gmap_id": "cafe",
                    "name": "Cafe",
                    "categories": "Coffee shop",
                    "price": "$",
                    "lat": 41.827,
                    "lng": -71.405,
                    "hours": json.dumps([["Saturday", "7AM–6PM"]]),
                },
                {
                    "gmap_id": "far",
                    "name": "Far Beach",
                    "categories": "Beach",
                    "price": "",
                    "lat": 41.45,
                    "lng": -71.45,
                    "hours": json.dumps([["Saturday", "Open 24 hours"]]),
                },
            ]
        )
        self.by_id = {g: i for i, g in enumerate(self.places["gmap_id"])}
        self.hours = [parse_hours(h) for h in self.places["hours"]]


class StubMaps:
    def __init__(self, index):
        self.index = index

    def opening_hours(self, pid, weekday):
        return self.index.hours[self.index.by_id[pid]].get(weekday)

    def travel_minutes(self, a, b, mode="walk"):
        return estimate_travel_minutes(a[0], a[1], b[0], b[1], mode)


REQ = {
    "start": "09:00",
    "end": "18:00",
    "weekday": 5,
    "budget": 100,
    "group_size": 2,
    "mode": "walk",
    "max_leg_minutes": 20,
    "origin": {"name": "start", "lat": 41.8268, "lng": -71.4025},
}


def check(stops, **changes):
    idx = StubIndex()
    return {p["type"] for p in validate({"stops": stops}, {**REQ, **changes}, idx, StubMaps(idx))}


def test_good_plan_passes():
    assert (
        check(
            [
                {"place_id": "cafe", "arrive": "09:30", "leave": "10:15"},
                {"place_id": "museum", "arrive": "10:30", "leave": "12:00"},
            ]
        )
        == set()
    )


def test_each_violation_type():
    assert "closed" in check(
        [{"place_id": "museum", "arrive": "09:15", "leave": "10:00"}]
    )  # opens at 10
    assert "closed" in check(
        [{"place_id": "museum", "arrive": "11:00", "leave": "12:00"}], weekday=0
    )
    assert {"travel_time", "leg_too_long"} <= check(
        [{"place_id": "far", "arrive": "09:10", "leave": "10:00"}]
    )
    assert "over_budget" in check(
        [{"place_id": "museum", "arrive": "10:30", "leave": "12:00"}], budget=10
    )
    assert "bad_time" in check([{"place_id": "cafe", "arrive": "17:30", "leave": "18:30"}])
    assert "unknown_place" in check([{"place_id": "nope", "arrive": "10:00", "leave": "11:00"}])
    assert check([]) == {"empty"}
