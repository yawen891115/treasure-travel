"""Talk to the agent once and watch every tool call.

python scripts/try_agent.py                       # real model (needs ANTHROPIC_API_KEY in .env)
python scripts/try_agent.py --fake                # free scripted planner
python scripts/try_agent.py "2 of us on Sunday from 10:00, seafood and parks, 3 stops"
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv  # noqa: E402

from agent.agent import TripAgent  # noqa: E402
from agent.llm import ClaudeLLM, FakeLLM  # noqa: E402
from agent.maps import make_maps  # noqa: E402
from src import config  # noqa: E402
from src.serving import PlaceIndex  # noqa: E402

load_dotenv(config.ROOT / ".env")
ap = argparse.ArgumentParser()
ap.add_argument(
    "text",
    nargs="?",
    default="Two of us on Saturday from 10:00 to 17:00, "
    "budget $100 total, we love art museums and coffee, walking. Please plan 3 stops.",
)
ap.add_argument("--fake", action="store_true")
args = ap.parse_args()

index = PlaceIndex()
agent = TripAgent(FakeLLM() if args.fake else ClaudeLLM(), index, make_maps(index))
out = agent.run(args.text, candidates=index.search(args.text, k=10))

for m in out["messages"][1:]:  # replay the conversation
    for b in m["content"]:
        kind = getattr(b, "type", None) or b.get("type")
        if kind == "tool_use":
            print(f"-> {b.name}({json.dumps(b.input)[:150]})")
        elif kind == "tool_result":
            print(f"   <- {b['content'][:150]}")
        elif kind == "text" and b.text:
            print(f"model: {b.text[:300]}")
print("\nITINERARY:")
for s in (out["itinerary"] or {}).get("stops", []):
    print(f"  {s['arrive']}-{s['leave']}  {s.get('name', s['place_id'])}")
usage = out["usage"]
print(f"\nsteps={out['steps']}  tokens in={usage['input_tokens']} out={usage['output_tokens']}")
