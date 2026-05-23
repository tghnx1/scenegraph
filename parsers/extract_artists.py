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
DEFAULT_INPUT_PATH = JSON_DIR / "events_by_year"
DEFAULT_OUTPUT_PATH = JSON_DIR / "artists.json"
YEARLY_FILE_PREFIX = "ra_berlin_past_events_"


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


def iter_event_files(input_path: Path) -> list[Path]:
    if input_path.is_dir() or input_path.suffix.lower() != ".json":
        files = sorted(input_path.glob(f"{YEARLY_FILE_PREFIX}*.json"), reverse=True)
        if files:
            return files
        raise FileNotFoundError(f"No yearly event files found in {input_path}")

    if not input_path.exists():
        raise FileNotFoundError(f"Events input does not exist: {input_path}")

    return [input_path]


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
    parser.add_argument(
        "--dedup-db",
        action="store_true",
        help="Skip artists that already exist in the database (artists.ra_artist_id).",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=os.environ.get("DATABASE_URL"),
        help="Database URL used when --dedup-db is enabled. Defaults to DATABASE_URL env var.",
    )
    return parser.parse_args()


def load_existing_artist_ids_from_db(database_url: str) -> set[str]:
    try:
        import psycopg  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "psycopg is required for --dedup-db. Install it or run with a Python env that has psycopg."
        ) from exc

    existing_ids: set[str] = set()
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT ra_artist_id
                FROM artists
                WHERE ra_artist_id IS NOT NULL
                """
            )
            for row in cursor.fetchall():
                value = row[0]
                if value is not None:
                    existing_ids.add(str(value))
    return existing_ids


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    unique_artists = {}
    skipped_existing = 0
    existing_artist_ids: set[str] = set()
    if args.dedup_db:
        if not args.database_url:
            raise ValueError("--dedup-db requires --database-url or DATABASE_URL")
        existing_artist_ids = load_existing_artist_ids_from_db(args.database_url)
        print(f"Loaded {len(existing_artist_ids)} existing artists from DB for dedup")

    event_files = iter_event_files(args.input)

    for event_file in event_files:
        with event_file.open("r", encoding="utf-8") as infile:
            events = json.load(infile)

        if not isinstance(events, list):
            raise ValueError(f"{event_file} must contain a JSON array")

        for event in events:
            artists = event.get("artists", [])
            for artist in artists:
                artist_id = artist.get("id")
                content_url = artist.get("contentUrl")

                if not artist_id or not content_url:
                    continue

                artist_id = str(artist_id)
                if artist_id in existing_artist_ids:
                    skipped_existing += 1
                    continue

                if artist_id not in unique_artists:
                    unique_artists[artist_id] = {
                        "id": artist_id,
                        "url": f"https://ra.co{content_url}/biography",
                    }

    write_json_atomic(args.output, list(unique_artists.values()))

    print(
        f"Saved {len(unique_artists)} artists to {args.output} from {len(event_files)} event file(s); "
        f"skipped_existing_db_artists={skipped_existing}"
    )


if __name__ == "__main__":
    main()
