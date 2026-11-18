"""Turn a Google Forms CSV export into (1) a requirements summary and (2) agent test requests.

    python scripts/survey_to_requests.py survey/responses.csv

Writes survey/requests_from_survey.jsonl and survey/survey_summary.md.
"""

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.constraints import DAYS  # noqa: E402
from src.serving import PlaceIndex  # noqa: E402

Q = {
    "group": "How many people are in your group?",
    "day": "Which day would you go?",
    "start": "What time would you start?",
    "end": "What time would you finish?",
    "budget": "Total budget for the group (USD)",
    "likes": "What do you enjoy? (pick up to 3)",
    "mode": "How would you get around?",
    "leg": "Longest travel time you accept between stops (minutes)",
    "origin": "Where would you start? (a place name)",
    "stops": "How many stops would you like?",
    "pain": "What annoys you most about planning a day trip today?",
    "use": "Would you use an app that plans the day for you?",
}
LIKE_TO_KEY = {
    "art": "art",
    "history": "history",
    "nature": "nature",
    "coffee": "coffee",
    "seafood": "seafood",
    "pizza": "pizza",
    "nightlife": "nightlife",
    "shopping": "shopping",
    "family": "family",
}


def to_hhmm(text):
    """Google Forms exports times like '10:00:00 AM'."""
    for fmt in ("%I:%M:%S %p", "%I:%M %p", "%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(str(text).strip(), fmt).strftime("%H:%M")
        except ValueError:
            pass
    raise ValueError(f"unreadable time {text!r}")


def main(csv_path):
    csv_path = Path(csv_path)
    source = "synthetic_example" if csv_path.name == "sample_responses.csv" else "survey"
    df = pd.read_csv(csv_path)
    index = PlaceIndex()
    requests, skipped = [], 0
    for k, row in df.iterrows():
        try:
            likes = [
                LIKE_TO_KEY[x.strip().lower()] for x in str(row[Q["likes"]]).split(",") if x.strip()
            ]
            found = index.find_by_name(row[Q["origin"]])  # match the start point by name
            if not found:
                raise ValueError("origin could not be matched; supply a known exact place name")
            hit = [found]
            if int(row[Q["group"]]) <= 0:
                raise ValueError("group size must be positive")
            mode = "walk" if str(row[Q["mode"]]).lower().startswith("walk") else "drive"
            weekday = DAYS.index(str(row[Q["day"]]).strip().lower())
            requests.append(
                {
                    "id": f"survey_{k:03d}",
                    "source": source,
                    "group_size": int(row[Q["group"]]),
                    "weekday": weekday,
                    "day_name": DAYS[weekday].title(),
                    "start": to_hhmm(row[Q["start"]]),
                    "end": to_hhmm(row[Q["end"]]),
                    "budget": int(float(row[Q["budget"]])),
                    "interests": likes[:3] or ["nature"],
                    "mode": mode,
                    "max_leg_minutes": int(row[Q["leg"]]),
                    "n_stops": int(row[Q["stops"]]),
                    "origin": {"name": hit[0]["name"], "lat": hit[0]["lat"], "lng": hit[0]["lng"]},
                }
            )
        except (KeyError, ValueError) as e:
            skipped += 1
            print(f"skipping row {k}: {e}")
    out = Path("survey/requests_from_survey.jsonl")
    out.write_text("\n".join(json.dumps(r) for r in requests) + "\n")

    likes = Counter(i for r in requests for i in r["interests"])
    per_person = pd.Series([r["budget"] / r["group_size"] for r in requests])
    summary = [
        "# Survey summary",
        "",
        f"Source: {source}. Example rows are not real survey evidence.",
        f"Responses: {len(df)} (usable: {len(requests)}, skipped: {skipped})",
        "",
        "## Most wanted interests",
        *[f"- {k}: {v}" for k, v in likes.most_common()],
        "",
        f"## Budget per person: median ${per_person.median():.0f}, "
        f"middle half ${per_person.quantile(0.25):.0f}"
        f"-${per_person.quantile(0.75):.0f}",
        "",
        f"## Getting around: {Counter(r['mode'] for r in requests)}",
        "",
        f"## Would use the app (1-5): mean "
        f"{pd.to_numeric(df[Q['use']], errors='coerce').mean():.1f}",
        "",
        "## Pain points (read these and group them into requirements)",
        *[f"- {p}" for p in df[Q["pain"]].dropna()],
    ]
    Path("survey/survey_summary.md").write_text("\n".join(summary) + "\n")
    print("\n".join(summary))
    print(f"\nwrote {len(requests)} requests -> {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "survey/sample_responses.csv")
