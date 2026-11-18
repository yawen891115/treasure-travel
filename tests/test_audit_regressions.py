import pytest

from agent.tools import ToolBox
from agent.maps import make_maps
from src.constraints import hhmm_to_min


@pytest.mark.parametrize("value", ["25:00", "10:99", "-1:00", "12:xx", "24:01", None, "9:00"])
def test_reject_invalid_clock(value):
    with pytest.raises(ValueError):
        hhmm_to_min(value)


def test_clock_boundaries():
    assert hhmm_to_min("00:00") == 0
    assert hhmm_to_min("24:00") == 1440


def test_current_turn_preferences_update_effective_constraints():
    box = ToolBox(None, None, request={"budget": 100}, preferences={"mode": "walk"})
    result = box.run(
        "update_trip_preferences",
        {"preferences": {"budget": 0, "day": "Monday", "mode": "drive", "group_size": 2}},
    )
    assert "error" not in result
    assert box.request["budget"] == 0
    assert box.request["weekday"] == 0
    assert box.request["mode"] == "drive"
    assert box.run("check_budget", {"place_ids": []})["budget"] == 0
    assert "error" in box.run("update_trip_preferences", {"preferences": {"group_size": -1}})
    assert box.request["group_size"] == 2


def test_empty_plan_not_accepted():
    box = ToolBox(None, None)
    assert "error" in box.run("submit_itinerary", {"stops": []})
    assert box.submitted is None


def test_google_mode_does_not_silently_fall_back(monkeypatch):
    monkeypatch.setenv("MAPS_MODE", "google")
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GOOGLE_MAPS_API_KEY"):
        make_maps(None)


def test_unadvertised_tool_rejected():
    box = ToolBox(None, None)
    assert box.run("loc", {"place_id": "start"}) == {"error": "unknown tool"}


def test_unknown_hours_not_counted_as_verified():
    from agent.validator import validate
    from test_validator import REQ, StubIndex, StubMaps

    idx = StubIndex()
    idx.hours[0] = {}
    issues = validate(
        {"stops": [{"place_id": "museum", "arrive": "10:30", "leave": "11:30"}]},
        REQ,
        idx,
        StubMaps(idx),
    )
    assert "unknown_hours" in {v["type"] for v in issues}


def test_rerank_unknown_hours_not_passed():
    from src.rerank import PlaceConstraints
    from test_validator import StubIndex

    idx = StubIndex()
    cons = PlaceConstraints(idx.places)
    assert cons.violation(0, 2, 600, 60, (41.826, -71.407), 20) == "unknown_hours"


@pytest.mark.parametrize(
    "categories",
    [["Barber shop"], ["Parking lot"], ["Parking garage"], ["Supermarket"], ["Pharmacy"]],
)
def test_nontravel_substrings_excluded(categories):
    from src.data_prep import is_travel_place

    assert not is_travel_place(categories)


@pytest.mark.parametrize(
    "categories",
    [
        ["Bar"],
        ["Park"],
        ["Art museum"],
        ["Seafood restaurant"],
        ["Farmers market"],
        ["Coffee shop"],
    ],
)
def test_real_travel_categories_retained(categories):
    from src.data_prep import is_travel_place

    assert is_travel_place(categories)


def test_parking_substring_does_not_make_gallery_free():
    from src.constraints import estimate_cost

    assert estimate_cost("", "Art gallery, Parking lot") == 20


def test_partial_topk_matches_exact_stable_full_sort():
    import numpy as np
    from src.ranker import top_k

    rng = np.random.default_rng(42)
    scores = rng.integers(0, 10, size=(10, 100)).astype(float)
    seen = [np.array([1, 2, 7])] * 10
    expected = scores.copy()
    expected[:, [1, 2, 7]] = -np.inf
    expected = np.argsort(-expected, axis=1, kind="stable")[:, :5]
    assert np.array_equal(top_k(scores, seen, 5), expected)
