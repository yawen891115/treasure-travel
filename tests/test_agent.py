"""Agent loop with the fake model. Needs the FAKE pipeline outputs (see README)."""

import pytest

from src import config


@pytest.fixture(scope="module")
def index():
    if not (config.ARTIFACTS / "item_stats.npz").exists():
        pytest.skip("run the pipeline on FAKE data first (scripts 00, 01, 02)")
    from src.serving import PlaceIndex

    return PlaceIndex()


def test_agent_with_tools_checks_hours_and_submits(index):
    from agent.agent import TripAgent
    from agent.llm import FakeLLM
    from agent.maps import OfflineMaps

    agent = TripAgent(FakeLLM(), index, OfflineMaps(index), use_tools=True)
    out = agent.run("Two of us on Saturday from 10:00, art museums and coffee, 3 stops")
    assert out["itinerary"] and len(out["itinerary"]["stops"]) >= 1
    assert "get_opening_hours" in out["tool_calls"] and out["tool_calls"][-1] == "submit_itinerary"


def test_tools_return_errors_instead_of_crashing(index):
    from agent.maps import OfflineMaps
    from agent.tools import ToolBox

    box = ToolBox(index, OfflineMaps(index))
    assert "error" in box.run("get_opening_hours", {"place_id": "does-not-exist", "day": "Monday"})
    assert "error" in box.run(
        "submit_itinerary", {"stops": [{"place_id": "x", "arrive": "10", "leave": "11"}]}
    )
