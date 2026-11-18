"""Download the official UCSD Rhode Island research benchmark with provenance.

The source requests citations; no commercial redistribution license is inferred.
Raw review text/names are not used by the modeling pipeline. Do not redistribute raw data.
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://mcauleylab.ucsd.edu/public_datasets/gdrive/googlelocal/"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--state", default="Massachusetts", choices=["Massachusetts", "Rhode_Island"]
    )
    args = parser.parse_args()
    directory = ROOT / "data" / "raw"
    directory.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name in (f"meta-{args.state}.json.gz", f"review-{args.state}_10.json.gz"):
        path = directory / name
        temp = directory / (name + ".part")
        digest = hashlib.sha256()
        with requests.get(BASE + name, stream=True, timeout=60) as response:
            response.raise_for_status()
            with temp.open("wb") as output:
                for chunk in response.iter_content(1024 * 1024):
                    output.write(chunk)
                    digest.update(chunk)
        temp.replace(path)
        manifest.append(
            {
                "file": name,
                "url": BASE + name,
                "bytes": path.stat().st_size,
                "sha256": digest.hexdigest(),
                "retrieved_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
        print(f"Downloaded {name}: {path.stat().st_size:,} bytes")
    if args.state == "Massachusetts":
        url = (
            "https://gisportal.boston.gov/arcgis/rest/services/Planning/OpenData/MapServer/9/query"
            "?where=1%3D1&outFields=*&outSR=4326&f=geojson"
        )
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        boundary = response.json()
        if not boundary.get("features"):
            raise ValueError("Official Boston boundary has no features")
        (directory / "boston_boundary.geojson").write_text(json.dumps(boundary))
        manifest.append(
            {
                "file": "boston_boundary.geojson",
                "url": url,
                "retrieved_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
    (directory / "source_manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
