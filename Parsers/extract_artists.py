import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent


def resolve_data_dir(default_root: Path) -> Path:
    override = os.environ.get("SCENEGRAPH_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return default_root / "data"


DATA_DIR = resolve_data_dir(SCRIPT_DIR)
JSON_DIR = DATA_DIR / "json"
DEFAULT_INPUT_PATH = JSON_DIR / "ra_berlin_past_events.json"
DEFAULT_OUTPUT_PATH = JSON_DIR / "artists.json"


def write_json_atomic(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
        ) as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            temp_path = Path(tmp.name)
        temp_path.replace(path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Path to the past events JSON file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path to the extracted artists JSON file",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.input.open("r", encoding="utf-8") as infile:
        events = json.load(infile)

    unique_artists = {}

    for event in events:
        artists = event.get("artists", [])
        for artist in artists:
            artist_id = artist.get("id")
            content_url = artist.get("contentUrl")

            if artist_id and content_url and artist_id not in unique_artists:
                unique_artists[artist_id] = {
                    "id": artist_id,
                    "url": f"https://ra.co{content_url}/biography",
                }

    write_json_atomic(args.output, list(unique_artists.values()))

    print(f"Saved {len(unique_artists)} artists to {args.output}")


if __name__ == "__main__":
    main()
