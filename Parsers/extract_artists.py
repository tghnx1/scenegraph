import argparse
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
JSON_DIR = SCRIPT_DIR / "data" / "json"
DEFAULT_INPUT_PATH = JSON_DIR / "ra_berlin_past_events.json"
DEFAULT_OUTPUT_PATH = JSON_DIR / "artists.json"


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

    with args.output.open("w", encoding="utf-8") as outfile:
        json.dump(list(unique_artists.values()), outfile, ensure_ascii=False, indent=2)

    print(f"Saved {len(unique_artists)} artists to {args.output}")


if __name__ == "__main__":
    main()
