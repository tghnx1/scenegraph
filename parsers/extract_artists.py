import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent


BIO_COMPLETE_STATUSES = {"ok", "not_found", "empty", "manually_edited"}


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
        help=(
            "Skip only DB artists whose biography is already complete or terminal. "
            "Existing artists with missing/failed/pending biographies are still emitted for refresh."
        ),
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=os.environ.get("DATABASE_URL"),
        help="Database URL used when --dedup-db is enabled. Defaults to DATABASE_URL env var.",
    )
    parser.add_argument(
        "--existing-artist-ids-file",
        type=Path,
        default=None,
        help="Optional newline-delimited file of RA artist IDs to skip.",
    )
    return parser.parse_args()


def normalize_optional_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def artist_bio_is_complete(row: dict[str, Any] | None) -> bool:
    if row is None:
        return False

    status = normalize_optional_text(row.get("biography_status")).casefold()
    if status == "manually_edited":
        return True
    if normalize_optional_text(row.get("biography")):
        return True
    return status in BIO_COMPLETE_STATUSES


def load_existing_artist_bio_state_from_db(database_url: str) -> dict[str, dict[str, Any]]:
    try:
        import psycopg  # type: ignore
        from psycopg.rows import dict_row  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "psycopg is required for --dedup-db. Install it or run with a Python env that has psycopg."
        ) from exc

    existing: dict[str, dict[str, Any]] = {}
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT ra_artist_id, biography, biography_status
                FROM artists
                WHERE ra_artist_id IS NOT NULL
                """
            )
            for row in cursor.fetchall():
                value = row.get("ra_artist_id")
                if value is not None:
                    existing[str(value)] = dict(row)
    return existing


def load_existing_artist_ids_from_file(path: Path) -> set[str]:
    existing_ids: set[str] = set()
    if not path.exists():
        return existing_ids
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            value = raw_line.strip()
            if value:
                existing_ids.add(value)
    return existing_ids


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    unique_artists = {}
    skipped_existing = 0
    refresh_existing = 0
    existing_artist_state: dict[str, dict[str, Any]] = {}
    existing_artist_ids: set[str] = set()
    if args.dedup_db:
        if not args.database_url:
            raise ValueError("--dedup-db requires --database-url or DATABASE_URL")
        existing_artist_state = load_existing_artist_bio_state_from_db(args.database_url)
        existing_artist_ids = set(existing_artist_state)
        print(f"Loaded {len(existing_artist_ids)} existing artists from DB for bio-aware dedup")
    if args.existing_artist_ids_file:
        file_ids = load_existing_artist_ids_from_file(args.existing_artist_ids_file)
        before = len(existing_artist_ids)
        existing_artist_ids.update(file_ids)
        print(
            f"Loaded {len(file_ids)} existing artists from file {args.existing_artist_ids_file} for dedup; "
            f"dedup set size: {before} -> {len(existing_artist_ids)}"
        )

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
                    if artist_id not in existing_artist_state or artist_bio_is_complete(existing_artist_state[artist_id]):
                        skipped_existing += 1
                        continue
                    refresh_existing += 1

                if artist_id not in unique_artists:
                    unique_artists[artist_id] = {
                        "id": artist_id,
                        "url": f"https://ra.co{content_url}/biography",
                    }

    write_json_atomic(args.output, list(unique_artists.values()))

    print(
        f"Saved {len(unique_artists)} artists to {args.output} from {len(event_files)} event file(s); "
        f"skipped_existing_complete_artists={skipped_existing}; "
        f"included_existing_refresh_artists={refresh_existing}"
    )


if __name__ == "__main__":
    main()
