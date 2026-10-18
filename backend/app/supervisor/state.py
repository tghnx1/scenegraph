from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


LATEST_RUN_SQL = """
SELECT id, pipeline_name, status, min_date, max_date,
       event_count, artist_count, events_imported, artists_imported,
       event_tags, artist_tags, event_embeddings, artist_embeddings,
       error, started_at, finished_at, updated_at
FROM import_runs
ORDER BY started_at DESC, id DESC
LIMIT 1
"""

RUN_SQL = """
SELECT id, pipeline_name, status, min_date, max_date,
       event_count, artist_count, events_imported, artists_imported,
       event_tags, artist_tags, event_embeddings, artist_embeddings,
       error, started_at, finished_at, updated_at
FROM import_runs
WHERE id = %s
"""

STAGES_SQL = """
SELECT stage_name, status, duration_ms, error, started_at, finished_at, updated_at
FROM import_run_stages
WHERE import_run_id = %s
ORDER BY id ASC
"""

QUARANTINE_SQL = """
SELECT entity_type,
       COUNT(*) AS unresolved_count,
       COALESCE(SUM(attempt_count), 0) AS attempts
FROM ingestion_quarantine
WHERE resolved_at IS NULL
GROUP BY entity_type
ORDER BY entity_type ASC
"""


class ReadOnlyConnection(Protocol):
    def cursor(self) -> Any: ...


class TelegramSink(Protocol):
    def send(self, message: str) -> None: ...


def sanitize(value: object, *, limit: int = 512) -> str:
    text = str(value)
    text = re.sub(r"Bearer\s+\S+", "Bearer [REDACTED]", text, flags=re.IGNORECASE)
    text = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[REDACTED_KEY]", text)
    text = re.sub(
        r"(?i)(api[_ -]?key|token|password|secret)\s*[:=]\s*\S+",
        r"\1=[REDACTED]",
        text,
    )
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _row_value(row: Any, key: str, index: int) -> Any:
    return row.get(key) if isinstance(row, dict) else row[index]


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_timestamp(value: Any) -> str | None:
    return None if value is None else sanitize(value, limit=80)


@dataclass(frozen=True)
class StageSnapshot:
    name: str
    status: str
    duration_ms: int | None
    error: str | None
    started_at: str | None
    finished_at: str | None
    updated_at: str | None


@dataclass(frozen=True)
class QuarantineSummary:
    entity_type: str
    unresolved_count: int
    attempts: int


@dataclass(frozen=True)
class ImportRunSnapshot:
    run_id: str
    pipeline_name: str
    status: str
    min_date: str | None
    max_date: str | None
    event_count: int
    artist_count: int
    events_imported: int
    artists_imported: int
    event_tags: int
    artist_tags: int
    event_embeddings: int
    artist_embeddings: int
    error: str | None
    started_at: str | None
    finished_at: str | None
    updated_at: str | None
    stages: tuple[StageSnapshot, ...]
    quarantine: tuple[QuarantineSummary, ...]

    @property
    def remaining_events(self) -> int:
        return max(self.event_count - self.events_imported, 0)

    @property
    def remaining_artists(self) -> int:
        return max(self.artist_count - self.artists_imported, 0)

    def public_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["stages"] = [asdict(stage) for stage in self.stages]
        result["quarantine"] = [asdict(item) for item in self.quarantine]
        result["progress"] = {
            "events": {"total": self.event_count, "completed": self.events_imported, "remaining": self.remaining_events},
            "artists": {"total": self.artist_count, "completed": self.artists_imported, "remaining": self.remaining_artists},
        }
        return result


class ProductRunReader:
    """Read-only projection of durable Scenegraph ingestion state."""

    def __init__(self, connection: ReadOnlyConnection) -> None:
        self.connection = connection

    def read(self, run_id: int | None = None) -> ImportRunSnapshot | None:
        with self.connection.cursor() as cursor:
            cursor.execute(LATEST_RUN_SQL if run_id is None else RUN_SQL, () if run_id is None else (run_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            actual_run_id = _safe_int(_row_value(row, "id", 0))
            cursor.execute(STAGES_SQL, (actual_run_id,))
            stage_rows = cursor.fetchall()
            cursor.execute(QUARANTINE_SQL)
            quarantine_rows = cursor.fetchall()

        stages = tuple(
            StageSnapshot(
                name=sanitize(_row_value(item, "stage_name", 0), limit=120),
                status=sanitize(_row_value(item, "status", 1), limit=40),
                duration_ms=_safe_int(_row_value(item, "duration_ms", 2)) if _row_value(item, "duration_ms", 2) is not None else None,
                error=sanitize(_row_value(item, "error", 3), limit=512) if _row_value(item, "error", 3) is not None else None,
                started_at=_safe_timestamp(_row_value(item, "started_at", 4)),
                finished_at=_safe_timestamp(_row_value(item, "finished_at", 5)),
                updated_at=_safe_timestamp(_row_value(item, "updated_at", 6)),
            )
            for item in stage_rows
        )
        quarantine = tuple(
            QuarantineSummary(
                entity_type=sanitize(_row_value(item, "entity_type", 0), limit=40),
                unresolved_count=_safe_int(_row_value(item, "unresolved_count", 1)),
                attempts=_safe_int(_row_value(item, "attempts", 2)),
            )
            for item in quarantine_rows
        )
        return ImportRunSnapshot(
            run_id=str(actual_run_id),
            pipeline_name=sanitize(_row_value(row, "pipeline_name", 1), limit=120),
            status=sanitize(_row_value(row, "status", 2), limit=40),
            min_date=_safe_timestamp(_row_value(row, "min_date", 3)),
            max_date=_safe_timestamp(_row_value(row, "max_date", 4)),
            event_count=_safe_int(_row_value(row, "event_count", 5)),
            artist_count=_safe_int(_row_value(row, "artist_count", 6)),
            events_imported=_safe_int(_row_value(row, "events_imported", 7)),
            artists_imported=_safe_int(_row_value(row, "artists_imported", 8)),
            event_tags=_safe_int(_row_value(row, "event_tags", 9)),
            artist_tags=_safe_int(_row_value(row, "artist_tags", 10)),
            event_embeddings=_safe_int(_row_value(row, "event_embeddings", 11)),
            artist_embeddings=_safe_int(_row_value(row, "artist_embeddings", 12)),
            error=sanitize(_row_value(row, "error", 13), limit=512) if _row_value(row, "error", 13) else None,
            started_at=_safe_timestamp(_row_value(row, "started_at", 14)),
            finished_at=_safe_timestamp(_row_value(row, "finished_at", 15)),
            updated_at=_safe_timestamp(_row_value(row, "updated_at", 16)),
            stages=stages,
            quarantine=quarantine,
        )


class JsonStateStore:
    """Small atomic JSON state store for the supervisor control plane."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"runs": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent, delete=False) as handle:
            json.dump(state, handle, sort_keys=True, indent=2)
            temporary_path = Path(handle.name)
        os.replace(temporary_path, self.path)


class DeterministicSupervisor:
    """Persist a safe run projection and notify without requiring an LLM."""

    def __init__(self, reader: ProductRunReader, store: JsonStateStore, telegram: TelegramSink) -> None:
        self.reader = reader
        self.store = store
        self.telegram = telegram

    def observe(self, run_id: int | None = None) -> dict[str, Any]:
        snapshot = self.reader.read(run_id)
        if snapshot is None:
            raise LookupError("import run not found")
        report = snapshot.public_dict()
        category = self._failure_category(snapshot)
        report["failure_category"] = category
        state = self.store.load()
        runs = state.setdefault("runs", {})
        previous = runs.get(snapshot.run_id, {})
        notification_category = category or ("succeeded" if snapshot.status == "succeeded" else None)
        notification_key = f"{snapshot.status}:{notification_category or 'none'}:{snapshot.error or ''}"
        report["observed_at"] = datetime.now(timezone.utc).isoformat()
        report["notification_key"] = notification_key
        runs[snapshot.run_id] = report
        self.store.save(state)
        if notification_category and notification_key != previous.get("notification_key"):
            self._notify(snapshot, notification_category)
        return report

    @staticmethod
    def _failure_category(snapshot: ImportRunSnapshot) -> str | None:
        if snapshot.status not in {"failed", "running"} and not any(stage.status == "failed" for stage in snapshot.stages):
            return None
        errors = [snapshot.error, *(stage.error for stage in snapshot.stages if stage.status == "failed")]
        if any(error and any(marker in error.casefold() for marker in ("quota", "usage limit", "rate limit")) for error in errors):
            return "quota_exhausted"
        if any(error and ("authentication" in error.casefold() or "invalid api key" in error.casefold()) for error in errors):
            return "authentication"
        return "unknown_system" if snapshot.status == "failed" else None

    def _notify(self, snapshot: ImportRunSnapshot, category: str) -> None:
        if category == "succeeded":
            self.telegram.send(
                f"Ingestion succeeded: run={snapshot.run_id}; events={snapshot.events_imported}; artists={snapshot.artists_imported}"
            )
        elif category == "quota_exhausted":
            self.telegram.send(f"Extraction paused: provider quota exhausted; run={snapshot.run_id}; remaining_events={snapshot.remaining_events}; remaining_artists={snapshot.remaining_artists}")
        elif category in {"authentication", "unknown_system"}:
            self.telegram.send(f"Ingestion requires attention: run={snapshot.run_id}; category={category}")
