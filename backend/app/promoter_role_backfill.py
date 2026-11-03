"""Durable, explicitly bounded promoter-role classification runs.

The caller must hold the session advisory lock while claiming and processing work.
Run and item transitions are committed by the caller together with the decisions.
"""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from psycopg import Connection
from psycopg.types.json import Jsonb
from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAIError, RateLimitError

from app.promoter_role_llm import InvalidRoleResponse, ProposedRole, RoleResponse, classify_with_llm
from app.event_tag_extraction import EventTagExtractionConfig
from app.promoter_role_store import EventInputChanged, load_event_input, save_llm_roles
from app.promoter_roles import CLASSIFIER_VERSION, EventRoleInput, classify_explicit_presenter
from app.promoter_roles import role_input_hash, role_input_snapshot

LOCK_KEY = 0x534750524F4C4553
MAX_EVENTS = 1000
MAX_ATTEMPTS = 3


def deterministic_response(event: EventRoleInput) -> RoleResponse | None:
    """Skip the provider only when every existing profile has explicit evidence."""
    decisions = []
    for profile in event.promoters:
        signal = classify_explicit_presenter(profile.name, event.venue_name, event.title)
        if signal.role == "unknown" or signal.evidence is None:
            return None
        decisions.append(ProposedRole(profile.id, signal.role, 1.0, signal.evidence))
    return RoleResponse(tuple(decisions), ()) if decisions else None


class BackfillBusy(RuntimeError):
    """Another classifier holds the worker lock."""


@dataclass(frozen=True, slots=True)
class PendingItem:
    event_id: int
    attempts: int


def config_hash(provider: str, model: str, reasoning_effort: str, endpoint: str = "", api_version: str = "") -> str:
    config = [CLASSIFIER_VERSION, provider, model, reasoning_effort, endpoint, api_version]
    return hashlib.sha256(json.dumps(config, separators=(",", ":")).encode()).hexdigest()


def extraction_config_hash(config: EventTagExtractionConfig) -> str:
    """Bind resumable work to provider endpoint and model, without storing credentials."""
    if config.provider == "kimi_code":
        endpoint = os.environ.get("KIMI_BASE_URL", "https://api.kimi.ai/coding/v1")
        api_version = ""
    elif config.provider == "moonshot":
        endpoint = os.environ.get("MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1")
        api_version = ""
    else:
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        api_version = os.environ.get("AZURE_OPENAI_CHAT_API_VERSION", "")
    return config_hash(config.provider, config.model, config.reasoning_effort, endpoint, api_version)


@contextmanager
def worker_lock(connection: Connection) -> Iterator[None]:
    """Keep the session lock across per-event commits and release on every exit."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_KEY,))
        if not cursor.fetchone()[0]:
            raise BackfillBusy("promoter classification worker is already running")
    try:
        yield
    finally:
        # Roll back an aborted transaction before trying to release the session lock.
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))
        connection.commit()


def create_run(connection: Connection, event_ids: tuple[int, ...], current_config_hash: str) -> int:
    """Create work only for an explicitly supplied, finite list of event IDs."""
    if not event_ids or len(event_ids) > MAX_EVENTS or len(set(event_ids)) != len(event_ids):
        raise ValueError("event IDs must be unique and number between 1 and 1000")
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM events WHERE id = ANY(%s)", (list(event_ids),))
        if cursor.fetchone()[0] != len(event_ids):
            raise ValueError("event scope contains unknown IDs")
        cursor.execute("""
            INSERT INTO promoter_role_backfill_run (scope, classifier_version, config_hash, status)
            VALUES (%s, %s, %s, 'queued') RETURNING id
        """, (Jsonb({"event_ids": list(event_ids)}), CLASSIFIER_VERSION, current_config_hash))
        run_id = cursor.fetchone()[0]
        cursor.executemany("""
            INSERT INTO promoter_role_backfill_item (run_id, event_id, status)
            VALUES (%s, %s, 'pending')
        """, [(run_id, event_id) for event_id in event_ids])
    return int(run_id)


def resume_run(connection: Connection, run_id: int, current_config_hash: str) -> None:
    """Resume only the original model and rule version, retaining completed work."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT classifier_version, config_hash, status FROM promoter_role_backfill_run WHERE id = %s FOR UPDATE", (run_id,))
        row = cursor.fetchone()
        if row is None:
            raise LookupError("classification run not found")
        if row[0] != CLASSIFIER_VERSION or row[1] != current_config_hash:
            raise ValueError("classification configuration changed; create a new run")
        if row[2] == "succeeded":
            return
        cursor.execute("""
            UPDATE promoter_role_backfill_run SET status = 'running',
              started_at = COALESCE(started_at, now()), completed_at = NULL, updated_at = now()
            WHERE id = %s
        """, (run_id,))
        cursor.execute("""
            UPDATE promoter_role_backfill_item SET status = 'pending', updated_at = now()
            WHERE run_id = %s AND status = 'running'
        """, (run_id,))


def claim_item(connection: Connection, run_id: int) -> PendingItem | None:
    """Claim the next pending item; failed items are not blindly retried."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT event_id, attempts FROM promoter_role_backfill_item
            WHERE run_id = %s AND status = 'pending' AND attempts < %s
            ORDER BY event_id LIMIT 1 FOR UPDATE
        """, (run_id, MAX_ATTEMPTS))
        row = cursor.fetchone()
        if row is None:
            return None
        cursor.execute("""
            UPDATE promoter_role_backfill_item SET status = 'running', attempts = attempts + 1, updated_at = now()
            WHERE run_id = %s AND event_id = %s
        """, (run_id, row[0]))
        return PendingItem(int(row[0]), int(row[1]) + 1)


def finish_item(connection: Connection, run_id: int, event_id: int, *, status: str, error_code: str | None = None, input_hash: str | None = None, input_tokens: int | None = None, output_tokens: int | None = None) -> None:
    if status not in {"pending", "succeeded", "failed"}:
        raise ValueError("invalid item status")
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE promoter_role_backfill_item SET status = %s, error_code = %s, input_hash = %s,
              input_tokens = %s, output_tokens = %s, updated_at = now()
            WHERE run_id = %s AND event_id = %s AND status = 'running'
        """, (status, error_code, input_hash, input_tokens, output_tokens, run_id, event_id))
        if cursor.rowcount != 1:
            raise LookupError("running item not found")


def _finish_run(connection: Connection, run_id: int, status: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE promoter_role_backfill_run SET status = %s,
              completed_at = CASE WHEN %s IN ('succeeded', 'failed') THEN now() ELSE NULL END,
              updated_at = now() WHERE id = %s
        """, (status, status, run_id))


def process_run(connection: Connection, run_id: int, current_config_hash: str) -> str:
    """Process one bounded run. Failures persist only safe categories, not provider text."""
    with worker_lock(connection):
        resume_run(connection, run_id, current_config_hash)
        connection.commit()
        while True:
            item = claim_item(connection, run_id)
            if item is None:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT count(*) FROM promoter_role_backfill_item WHERE run_id = %s AND status <> 'succeeded'", (run_id,))
                    remaining = cursor.fetchone()[0]
                status = "failed" if remaining else "succeeded"
                _finish_run(connection, run_id, status)
                connection.commit()
                return status
            connection.commit()
            source = load_event_input(connection, item.event_id)
            # Do not hold a transaction or row locks while waiting for the model.
            connection.commit()
            if source is None:
                finish_item(connection, run_id, item.event_id, status="failed", error_code="event_missing")
                connection.commit()
                continue
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 1 FROM promoter_event_classification
                    WHERE event_id = %s AND input_hash = %s AND config_hash = %s AND classifier_version = %s
                """, (item.event_id, role_input_hash(source), current_config_hash, CLASSIFIER_VERSION))
                already_classified = cursor.fetchone() is not None
            if already_classified:
                locked = load_event_input(connection, item.event_id, lock=True)
                if locked is not None and role_input_hash(locked) == role_input_hash(source):
                    finish_item(connection, run_id, item.event_id, status="succeeded", input_hash=role_input_hash(source))
                    connection.commit()
                    continue
                connection.rollback()
                finish_item(connection, run_id, item.event_id, status="pending", error_code="input_changed")
                _finish_run(connection, run_id, "paused")
                connection.commit()
                return "paused"
            connection.commit()
            try:
                response = deterministic_response(source)
                method = "rule" if response is not None else "llm"
                if response is None:
                    response = classify_with_llm(source)
                save_llm_roles(connection, source, response, method=method)
                with connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO promoter_event_classification (event_id, input_hash, input_snapshot, config_hash, classifier_version)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (event_id) DO UPDATE SET input_hash = EXCLUDED.input_hash,
                          input_snapshot = EXCLUDED.input_snapshot, config_hash = EXCLUDED.config_hash, classifier_version = EXCLUDED.classifier_version,
                          classified_at = now()
                    """, (item.event_id, role_input_hash(source), Jsonb(role_input_snapshot(source)), current_config_hash, CLASSIFIER_VERSION))
                finish_item(connection, run_id, item.event_id, status="succeeded", input_hash=role_input_hash(source),
                            input_tokens=response.input_tokens, output_tokens=response.output_tokens)
                connection.commit()
            except RateLimitError:
                connection.rollback()
                finish_item(connection, run_id, item.event_id, status="pending", error_code="provider_quota")
                # Quota exhaustion is not a failed attempt; a later invocation can resume.
                with connection.cursor() as cursor:
                    cursor.execute("UPDATE promoter_role_backfill_item SET attempts = attempts - 1 WHERE run_id = %s AND event_id = %s", (run_id, item.event_id))
                _finish_run(connection, run_id, "paused")
                connection.commit()
                return "paused"
            except (APIConnectionError, APITimeoutError, InternalServerError, EventInputChanged):
                connection.rollback()
                status = "pending" if item.attempts < MAX_ATTEMPTS else "failed"
                finish_item(connection, run_id, item.event_id, status=status, error_code="transient_failure")
                connection.commit()
                if status == "pending":
                    # Leave the bounded retry to the next explicit invocation.
                    _finish_run(connection, run_id, "paused")
                    connection.commit()
                    return "paused"
            except InvalidRoleResponse:
                connection.rollback()
                finish_item(connection, run_id, item.event_id, status="failed", error_code="invalid_model_response")
                connection.commit()
            except OpenAIError:
                connection.rollback()
                finish_item(connection, run_id, item.event_id, status="failed", error_code="provider_system_failure")
                _finish_run(connection, run_id, "failed")
                connection.commit()
                return "failed"
            except Exception:
                # This boundary records the failure but always propagates the programming/system error.
                connection.rollback()
                finish_item(connection, run_id, item.event_id, status="failed", error_code="system_failure")
                _finish_run(connection, run_id, "failed")
                connection.commit()
                raise
