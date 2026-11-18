"""Step 5: how often do plans break a constraint, with and without verification tools?

    python scripts/05_eval_agent.py --fake-llm --n 10     # free dry run, no API key needed
    python scripts/05_eval_agent.py --n 20                # billable; check provider prices
    python scripts/05_eval_agent.py --n 200               # the full evaluation

Both modes get the same request and the same candidate places from our recommender.
  llm_only   the model must plan from the list alone (it can only call submit_itinerary)
  llm_tools  the model can also check opening hours, travel times and the budget
The same validator judges both. Runs are appended to results/agent_runs.jsonl, so an interrupted
run continues where it stopped.
"""

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv  # noqa: E402

from agent.agent import TripAgent  # noqa: E402
from agent.llm import ClaudeLLM, FakeLLM  # noqa: E402
from agent.maps import OfflineMaps  # noqa: E402
from agent.validator import validate  # noqa: E402
from src import config  # noqa: E402
from src.serving import PlaceIndex  # noqa: E402

load_dotenv(config.ROOT / ".env")
PRICE_IN = float(os.environ["PRICE_IN_PER_MTOK"]) if os.environ.get("PRICE_IN_PER_MTOK") else None
PRICE_OUT = (
    float(os.environ["PRICE_OUT_PER_MTOK"]) if os.environ.get("PRICE_OUT_PER_MTOK") else None
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--fake-llm", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--modes", default="llm_only,llm_tools")
    args = ap.parse_args()

    index = PlaceIndex()
    maps = OfflineMaps(index)  # same free data for the tools and for the judge
    reqs = [
        json.loads(line)
        for line in (config.DATA_PROCESSED / "agent_requests.jsonl").read_text().splitlines()
        if line.strip()
    ][: args.n]
    tag = "fake" if args.fake_llm else os.environ.get("LLM_MODEL")
    if not tag:
        ap.error("Set LLM_MODEL before a real API evaluation")
    modes = args.modes.split(",")
    if set(modes) - {"llm_only", "llm_tools"} or args.n < 1 or args.workers < 1:
        ap.error("invalid modes, n, or workers")
    digest = hashlib.sha256(json.dumps(reqs, sort_keys=True).encode())
    for directory in (
        config.ROOT / "src",
        config.ROOT / "agent",
        config.DATA_PROCESSED,
        config.ARTIFACTS,
    ):
        for path in sorted(directory.glob("*")):
            if path.is_file() and path.suffix in {
                ".py",
                ".json",
                ".parquet",
                ".npz",
                ".npy",
                ".joblib",
            }:
                digest.update(path.name.encode())
                digest.update(path.read_bytes())
    digest.update(Path(__file__).read_bytes())
    digest.update(tag.encode())
    run_id = digest.hexdigest()[:12]
    safe_tag = "".join(c if c.isalnum() or c in "-_" else "_" for c in tag)
    runs_path = config.results_dir() / f"agent_runs_{safe_tag}_{run_id}.jsonl"
    done = set()
    if runs_path.exists():
        done = {(r["mode"], r["id"]) for r in map(json.loads, runs_path.read_text().splitlines())}

    def one(mode, req):
        llm = FakeLLM() if args.fake_llm else ClaudeLLM()
        agent = TripAgent(llm, index, maps, use_tools=(mode == "llm_tools"))
        cands = index.search(
            req["query"],
            near=(req["origin"]["lat"], req["origin"]["lng"]),
            max_minutes=2 * req["max_leg_minutes"],
            mode=req["mode"],
            k=12,
        )
        out = agent.run(req["text"], request=req, candidates=cands)
        problems = validate(out["itinerary"], req, index, maps)
        return {
            "mode": mode,
            "id": req["id"],
            "source": req["source"],
            "violations": problems,
            "n_stops": len((out["itinerary"] or {}).get("stops", [])),
            "tool_calls": out["tool_calls"],
            "steps": out["steps"],
            "usage": out["usage"],
            "itinerary": out["itinerary"],
        }

    jobs = [(m, r) for m in modes for r in reqs if (m, r["id"]) not in done]
    print(f"{len(jobs)} runs to do ({len(done)} already done) -> {runs_path.name}")
    with ThreadPoolExecutor(max_workers=args.workers) as pool, runs_path.open("a") as f:
        futures = {pool.submit(one, m, r): (m, r) for m, r in jobs}
        for k, fut in enumerate(as_completed(futures), start=1):
            try:
                row = fut.result()
            except Exception as e:  # one failed run should not stop the rest
                mode, req = futures[fut]
                row = {
                    "mode": mode,
                    "id": req["id"],
                    "source": req["source"],
                    "violations": [{"type": "execution_error", "detail": type(e).__name__}],
                    "n_stops": 0,
                    "tool_calls": [],
                    "steps": 0,
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                    "itinerary": None,
                }
                print("run failed:", type(e).__name__)
            f.write(json.dumps(row) + "\n")
            f.flush()
            if k % 10 == 0:
                print(f"  {k}/{len(jobs)} runs finished")
    summarize(runs_path, {r["id"] for r in reqs}, safe_tag + "_" + run_id)


def summarize(runs_path, ids, tag):
    rows = [r for r in map(json.loads, runs_path.read_text().splitlines()) if r["id"] in ids]
    state = config.dataset_state()
    lines = [
        f"# Agent evaluation ({tag})",
        "Synthetic/FakeLLM runs are integration checks, not evidence of LLM effectiveness.",
        "",
        f"Dataset: **{state}**"
        + (" (practice data - never report these numbers)" if state == "FAKE" else ""),
        "",
        "| Mode | Plans | Plans with violation or unverified hours | closed | "
        "travel_time | leg_too_long | "
        "over_budget | "
        "bad_time | no plan | unknown hours | execution errors | "
        "Avg tool calls | Est. cost (USD) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for mode in ("llm_only", "llm_tools"):
        rs = [r for r in rows if r["mode"] == mode]
        if not rs:
            continue
        bad = sum(1 for r in rs if r["violations"])
        types = Counter(t for r in rs for t in {v["type"] for v in r["violations"]})
        tin = sum(r["usage"]["input_tokens"] for r in rs)
        tout = sum(r["usage"]["output_tokens"] for r in rs)
        cost = (
            f"{tin / 1e6 * PRICE_IN + tout / 1e6 * PRICE_OUT:.2f}"
            if PRICE_IN is not None and PRICE_OUT is not None
            else "not configured"
        )
        if tag.startswith("fake"):
            cost = "0.00"

        def share(kind, types=types, n=len(rs)):
            return f"{types.get(kind, 0) / n:.0%}"

        lines.append(
            f"| {mode} | {len(rs)} | **{bad / len(rs):.1%}** | {share('closed')} | "
            f"{share('travel_time')} | "
            f"{share('leg_too_long')} | {share('over_budget')} | {share('bad_time')} | "
            f"{share('empty')} | {share('unknown_hours')} | {share('execution_error')} | "
            f"{sum(len(r['tool_calls']) for r in rs) / len(rs):.1f} | {cost} |"
        )
    src = Counter(r["source"] for r in rows if r["mode"] == "llm_tools")
    lines += [
        "",
        f"Request sources: {dict(src)}. Judge: offline hours + distance-based travel estimates.",
    ]
    out = config.results_dir() / f"agent_results_{tag}.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
