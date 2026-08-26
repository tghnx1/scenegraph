from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


BERLIN_TIMEZONE_NAME = "Europe/Berlin"
BERLIN_TIMEZONE = ZoneInfo(BERLIN_TIMEZONE_NAME)
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
DEFAULT_ARTIFACTS_DIR = Path("/tmp/scenegraph-import-runs")


def resolve_target_date(
    *,
    now: datetime | None = None,
    environ: Mapping[str, str] | None = None,
) -> date:
    environment = os.environ if environ is None else environ
    override = environment.get("DAILY_INGEST_DATE", "").strip()
    if override:
        try:
            parsed = date.fromisoformat(override)
        except ValueError as exc:
            raise ValueError(
                "DAILY_INGEST_DATE must use a valid YYYY-MM-DD calendar date"
            ) from exc
        if parsed.isoformat() != override:
            raise ValueError("DAILY_INGEST_DATE must use exact YYYY-MM-DD format")
        return parsed

    current = now or datetime.now(tz=BERLIN_TIMEZONE)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    berlin_today = current.astimezone(BERLIN_TIMEZONE).date()
    return berlin_today - timedelta(days=1)


def build_pipeline_command(target_date: date, artifacts_dir: Path) -> list[str]:
    target = target_date.isoformat()
    return [
        sys.executable,
        str(BACKEND_ROOT / "scripts" / "full_pipeline.py"),
        "--min-date",
        target,
        "--max-date",
        target,
        "--artifacts-dir",
        str(artifacts_dir),
        "--skip-bio",
    ]


def run_daily_ingestion(
    *,
    target_date: date | None = None,
    environ: Mapping[str, str] | None = None,
    run_command: Callable[..., subprocess.CompletedProcess[object]] = subprocess.run,
) -> int:
    environment = os.environ if environ is None else environ
    target = target_date or resolve_target_date(environ=environment)
    target_text = target.isoformat()
    artifacts_dir = Path(
        environment.get("DAILY_INGEST_ARTIFACTS_DIR", str(DEFAULT_ARTIFACTS_DIR))
    ).expanduser()

    print(f"Target timezone: {BERLIN_TIMEZONE_NAME}")
    print(f"Target date: {target_text}")
    print(f"min_date: {target_text}")
    print(f"max_date: {target_text}")
    print("Daily ingestion settings:")
    print("- scrape: enabled")
    print("- refresh-existing-events: enabled")
    print("- biography scraping: skipped")
    print("- tags: enabled")
    print("- embeddings: enabled")
    print("- validation: enabled")

    run_command(
        build_pipeline_command(target, artifacts_dir),
        cwd=REPO_ROOT,
        check=True,
    )

    print("Daily ingestion and validation succeeded; starting recommendation scheduler")
    run_command(
        [sys.executable, "-m", "app.recommendations.scheduler"],
        cwd=BACKEND_ROOT,
        check=True,
    )
    print("Recommendation scheduler completed successfully")
    return 0


def main() -> int:
    try:
        return run_daily_ingestion()
    except ValueError as exc:
        print(f"Daily ingestion configuration error: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(
            f"Daily ingestion failed; command exited with code {exc.returncode}",
            file=sys.stderr,
        )
        return exc.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
