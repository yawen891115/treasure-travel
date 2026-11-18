"""Compare two deterministic planners on identical requests and ranked candidates.

No model API or live Maps calls. This is NOT evidence of LLM/agent effectiveness.
Dataset hours, estimated travel and estimated visit costs define feasibility here.

    python scripts/06_eval_offline.py --n 200
"""

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.maps import OfflineMaps  # noqa: E402
from agent.offline import OfflinePlanner  # noqa: E402
from agent.validator import validate  # noqa: E402
from src import config  # noqa: E402
from src.constraints import hhmm_to_min, min_to_hhmm  # noqa: E402
from src.serving import PlaceIndex  # noqa: E402


def naive_plan(request, candidates):
    """Fixed schedule for the top candidates; does not check constraints."""
    t = hhmm_to_min(request["start"]) + 30
    stops = []
    for item in candidates[: int(request.get("n_stops", 3))]:
        stops.append(
            {"place_id": item["place_id"], "arrive": min_to_hhmm(t), "leave": min_to_hhmm(t + 60)}
        )
        t += 90
    return {"stops": stops}


def summarize(rows):
    """All requests, including failures/empty plans, remain in the denominator."""
    n = len(rows)
    if not n:
        return {"requests": 0}
    nonempty = [r for r in rows if r["n_stops"] > 0]
    types = Counter(v for r in rows for v in {p["type"] for p in r["violations"]})
    feasible = [r for r in rows if r["n_stops"] and not r["violations"]]
    return {
        "requests": n,
        "nonempty_plan_rate": len(nonempty) / n,
        "full_requested_stop_completion_rate": sum(
            r["n_stops"] >= r["requested_stops"] for r in rows
        )
        / n,
        "feasible_nonempty_plan_rate": len(feasible) / n,
        "feasible_full_completion_rate": sum(r["n_stops"] >= r["requested_stops"] for r in feasible)
        / n,
        "violation_or_unknown_or_no_plan_rate": sum(bool(r["violations"]) for r in rows) / n,
        "violation_or_unknown_among_nonempty_plans": (
            sum(bool(r["violations"]) for r in nonempty) / len(nonempty) if nonempty else None
        ),
        "unknown_hours_rate": types["unknown_hours"] / n,
        "execution_error_rate": types["execution_error"] / n,
        "average_stops": sum(r["n_stops"] for r in rows) / n,
        "violation_type_counts": dict(types),
    }


def evaluate(requests, index, maps, candidate_limit=12):
    rows = []
    planner = OfflinePlanner(index, maps)
    for req in requests:
        try:
            candidates = index.search(
                req["query"],
                near=(req["origin"]["lat"], req["origin"]["lng"]),
                max_minutes=2 * req["max_leg_minutes"],
                mode=req["mode"],
                k=candidate_limit,
            )
            candidate_error = None
        except Exception as exc:
            candidates, candidate_error = [], type(exc).__name__
        for mode in ["naive_scripted", "constraint_aware_rules"]:
            itinerary = None
            error = candidate_error
            try:
                if error:
                    raise ValueError("candidate generation failed")
                if mode == "naive_scripted":
                    itinerary = naive_plan(req, candidates)
                else:
                    # Structured request is authoritative; do not re-parse its generated prose.
                    itinerary = planner.run("", request=req, candidates=candidates)["itinerary"]
                violations = validate(itinerary, req, index, maps)
            except Exception as exc:
                error = error or type(exc).__name__
                violations = [{"type": "execution_error", "detail": error}]
            rows.append(
                {
                    "mode": mode,
                    "id": req["id"],
                    "source": req.get("source", "unknown"),
                    "requested_stops": int(req.get("n_stops", 3)),
                    "n_stops": len((itinerary or {}).get("stops", [])),
                    "candidate_ids": [c["place_id"] for c in candidates],
                    "violations": violations,
                    "itinerary": itinerary,
                }
            )
    return rows


def fingerprint(requests):
    digest = hashlib.sha256(json.dumps(requests, sort_keys=True).encode())
    paths = [Path(__file__)]
    for directory in [
        config.ROOT / "agent",
        config.ROOT / "src",
        config.DATA_PROCESSED,
        config.ARTIFACTS,
    ]:
        paths.extend(p for p in sorted(directory.iterdir()) if p.is_file())
    for path in paths:
        label = path.relative_to(config.ROOT) if path.is_relative_to(config.ROOT) else path.name
        digest.update(str(label).encode())
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--candidate-limit", type=int, default=12)
    args = parser.parse_args()
    if args.n < 1 or args.candidate_limit < 1:
        parser.error("n and candidate-limit must be positive")
    path = config.DATA_PROCESSED / "agent_requests.jsonl"
    requests = [json.loads(line) for line in path.read_text().splitlines() if line.strip()][
        : args.n
    ]
    if not requests:
        parser.error("no requests found")
    if len({r["id"] for r in requests}) != len(requests):
        parser.error("request IDs must be unique")
    index = PlaceIndex()
    rows = evaluate(requests, index, OfflineMaps(index), args.candidate_limit)
    summaries = {
        mode: summarize([r for r in rows if r["mode"] == mode])
        for mode in ["naive_scripted", "constraint_aware_rules"]
    }
    report = {
        "dataset": config.dataset_state(),
        "input_and_code_sha256": fingerprint(requests),
        "candidate_limit": args.candidate_limit,
        "request_sources": dict(Counter(r.get("source", "unknown") for r in requests)),
        "method": "Deterministic comparison; no LLM and no live Maps API",
        "judge": "dataset opening hours, distance-based travel, heuristic group costs",
        "limitations": [
            "Generated requests are not real-user outcomes.",
            "Feasibility uses estimates and historical hours, not live truth.",
            "Greedy planning is not globally optimal; partial plans are reported.",
            "Rule planner enforces these same constraints by construction; "
            "this is an integration benchmark, not an independent quality study.",
        ],
        "metrics": summaries,
        "runs": rows,
    }
    out_dir = config.results_dir()
    (out_dir / "offline_rules_results.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = [
        "# Deterministic offline planner comparison",
        "",
        f"Dataset: {report['dataset']}; requests: {len(requests)}.",
        f"Sources: {report['request_sources']}. Same candidates for each paired request.",
        "No LLM, paid API, or live Maps calls were used.",
        "",
        "| Mode | Nonempty plan | Full stop count | Feasible nonempty | Feasible full | "
        "Violation/unknown/no plan | Unknown hours | Avg stops |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for mode, result in summaries.items():
        rates = [
            result[key]
            for key in [
                "nonempty_plan_rate",
                "full_requested_stop_completion_rate",
                "feasible_nonempty_plan_rate",
                "feasible_full_completion_rate",
                "violation_or_unknown_or_no_plan_rate",
                "unknown_hours_rate",
            ]
        ]
        lines.append(
            f"| {mode} | "
            + " | ".join(f"{v:.1%}" for v in rates)
            + f" | {result['average_stops']:.2f} |"
        )
    lines += [
        "",
        "Rates use all requests as the denominator; failures are never dropped.",
        "A full stop count alone does not mean a feasible plan. Unknown hours are unverified.",
        "",
        *["- " + s for s in report["limitations"]],
        "",
        f"Input/code fingerprint: `{report['input_and_code_sha256']}`",
        "",
    ]
    markdown = "\n".join(lines)
    (out_dir / "offline_rules_results.md").write_text(markdown)
    print(markdown)


if __name__ == "__main__":
    main()
