import importlib.util
from pathlib import Path

from test_offline_planner import REQ, StubIndex, StubMaps

PATH = Path(__file__).resolve().parents[1] / "scripts" / "06_eval_offline.py"
SPEC = importlib.util.spec_from_file_location("eval_offline", PATH)
eval_offline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(eval_offline)


def test_summary_counts_failures_partial_and_unknown_in_denominator():
    rows = [
        {"n_stops": 3, "requested_stops": 3, "violations": [{"type": "unknown_hours"}]},
        {"n_stops": 1, "requested_stops": 3, "violations": []},
        {"n_stops": 0, "requested_stops": 3, "violations": [{"type": "execution_error"}]},
        {"n_stops": 0, "requested_stops": 3, "violations": [{"type": "empty"}]},
    ]
    result = eval_offline.summarize(rows)
    assert result["requests"] == 4
    assert result["nonempty_plan_rate"] == 0.5
    assert result["full_requested_stop_completion_rate"] == 0.25
    assert result["feasible_nonempty_plan_rate"] == 0.25
    assert result["feasible_full_completion_rate"] == 0
    assert result["violation_or_unknown_or_no_plan_rate"] == 0.75
    assert result["unknown_hours_rate"] == 0.25
    assert result["average_stops"] == 1


def test_paired_modes_receive_identical_candidates():
    class Index(StubIndex):
        def search(self, query, k=100, **kwargs):
            return super().search(query, k)

    request = {**REQ, "id": "test", "source": "synthetic", "n_stops": 3}
    rows = eval_offline.evaluate([request], Index(), StubMaps())
    assert len(rows) == 2
    assert rows[0]["candidate_ids"] == rows[1]["candidate_ids"]
    assert rows[0]["n_stops"] == 3
    assert rows[1]["n_stops"] == 2
    assert rows[0]["violations"]
    assert rows[1]["violations"] == []


def test_candidate_failure_is_recorded_for_both_modes():
    class BrokenIndex:
        def search(self, *args, **kwargs):
            raise RuntimeError("failure")

    rows = eval_offline.evaluate([{**REQ, "id": "test"}], BrokenIndex(), StubMaps())
    assert len(rows) == 2
    assert all(r["violations"][0]["type"] == "execution_error" for r in rows)
