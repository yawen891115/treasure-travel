"""Step 1: raw Google Local files -> clean tables in data/processed/.

python scripts/01_prepare_data.py                 # uses Rhode_Island (see src/config.py)
python scripts/01_prepare_data.py --state FAKE    # practice run on fake data
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config  # noqa: E402
from src.data_prep import prepare  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--state", default=config.STATE, help="e.g. Rhode_Island, Vermont, FAKE")
args = parser.parse_args()

meta = config.DATA_RAW / f"meta-{args.state}.json.gz"
review = config.DATA_RAW / f"review-{args.state}_10.json.gz"
for path in (meta, review):
    if not path.exists():
        sys.exit(
            f"Missing file: {path}\n"
            "Download it first (see guide chapter 3) or run with --state FAKE."
        )
prepare(meta, review, state=args.state)
