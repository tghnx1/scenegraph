"""Run durable backfill transitions against a real PostgreSQL schema."""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import httpx
from openai import RateLimitError
from psycopg import sql

from app import promoter_role_backfill as backfill
from app.promoter_role_llm import ProposedRole, RoleResponse
from app.promoter_role_eligibility import eligible_promoters
from app.promoter_role_queue import enqueue_changed_events, enqueue_imported_ra_events
from app.promoter_role_store import EventInputChanged


@pytest.fixture
def database():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL is required for PostgreSQL integration")
    schema = "test_role_backfill_" + uuid4().hex
    migration = Path(__file__).resolve().parents[1] / "prisma/migrations/20261103000000_promoter_event_roles/migration.sql"
    with psycopg.connect(url) as connection:
        try:
            connection.execute(sql.SQL("CREATE SCHEMA {} ").format(sql.Identifier(schema)))
            connection.execute(sql.SQL("SET search_path TO {} ").format(sql.Identifier(schema)))
            connection.execute("CREATE TABLE events (id BIGINT PRIMARY KEY, title TEXT, description_text TEXT, venue_id BIGINT, ra_event_id TEXT)")
            connection.execute("CREATE TABLE promoters (id BIGINT PRIMARY KEY, name TEXT)")
            connection.execute("CREATE TABLE venues (id BIGINT PRIMARY KEY, name TEXT)")
            connection.execute("CREATE TABLE event_promoters (event_id BIGINT, promoter_id BIGINT)")
            connection.execute(migration.read_text())
            connection.execute("INSERT INTO events VALUES (1, '8MM live', NULL, 1, 'ra1'), (2, 'Other live', NULL, NULL, 'ra2')")
            connection.execute("INSERT INTO venues VALUES (1, '8MM')")
            connection.execute("INSERT INTO promoters VALUES (1, '8MM'), (2, 'Other')")
            connection.execute("INSERT INTO event_promoters VALUES (1, 1), (2, 2)")
            connection.commit()
            yield connection
        finally:
            connection.rollback()
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
            connection.commit()


def test_resume_does_not_repeat_completed_events(database, monkeypatch):
    calls = []

    def classify(event):
        calls.append(event.event_id)
        if calls == [1, 2]:
            raise EventInputChanged("test interruption")
        return RoleResponse((ProposedRole(event.event_id, "organizer", 1, "presents"),), ())

    monkeypatch.setattr(backfill, "classify_with_llm", classify)
    run_id = backfill.create_run(database, (1, 2), "config")
    database.commit()
    assert backfill.process_run(database, run_id, "config") == "paused"
    assert backfill.process_run(database, run_id, "config") == "succeeded"
    assert calls == [1, 2, 2]
    rows = database.execute("SELECT event_id, status, attempts FROM promoter_role_backfill_item ORDER BY event_id").fetchall()
    assert rows == [(1, "succeeded", 1), (2, "succeeded", 2)]


def test_config_change_cannot_resume(database):
    run_id = backfill.create_run(database, (1,), "old")
    database.commit()
    with pytest.raises(ValueError, match="configuration changed"):
        backfill.process_run(database, run_id, "new")


def test_retries_are_bounded(database, monkeypatch):
    monkeypatch.setattr(backfill, "classify_with_llm", lambda event: (_ for _ in ()).throw(EventInputChanged("changed")))
    run_id = backfill.create_run(database, (1,), "config")
    database.commit()
    assert backfill.process_run(database, run_id, "config") == "paused"
    assert backfill.process_run(database, run_id, "config") == "paused"
    assert backfill.process_run(database, run_id, "config") == "failed"
    assert backfill.process_run(database, run_id, "config") == "failed"
    assert database.execute("SELECT attempts FROM promoter_role_backfill_item").fetchone() == (3,)


def test_quota_pauses_without_consuming_retry(database, monkeypatch):
    response = httpx.Response(429, request=httpx.Request("POST", "https://example.invalid"))

    def quota(_event):
        raise RateLimitError("quota", response=response, body=None)

    monkeypatch.setattr(backfill, "classify_with_llm", quota)
    run_id = backfill.create_run(database, (1,), "config")
    database.commit()
    assert backfill.process_run(database, run_id, "config") == "paused"
    assert database.execute("SELECT status, attempts, error_code FROM promoter_role_backfill_item").fetchone() == ("pending", 0, "provider_quota")


def test_dry_run_does_not_write(database):
    schema = database.execute("SELECT current_schema()").fetchone()[0]
    database.commit()
    env = os.environ.copy()
    env["PGOPTIONS"] = f"-c search_path={schema}"
    result = subprocess.run(
        [sys.executable, "-m", "app.promoter_role_backfill_cli", "--event-id", "1"],
        env=env, capture_output=True, text=True, check=True,
    )
    assert '"event_id": 1' in result.stdout
    assert database.execute("SELECT count(*) FROM promoter_role_backfill_run").fetchone() == (0,)
    assert database.execute("SELECT count(*) FROM promoter_event_role").fetchone() == (0,)


def test_worker_lock_prevents_concurrent_runs(database):
    with psycopg.connect(os.environ["DATABASE_URL"]) as second:
        with backfill.worker_lock(database):
            with pytest.raises(backfill.BackfillBusy):
                with backfill.worker_lock(second):
                    pass


def test_unknown_failure_is_recorded_and_propagated(database, monkeypatch):
    def broken(_event):
        raise RuntimeError("internal failure")

    monkeypatch.setattr(backfill, "classify_with_llm", broken)
    run_id = backfill.create_run(database, (1,), "config")
    database.commit()
    with pytest.raises(RuntimeError):
        backfill.process_run(database, run_id, "config")
    assert database.execute("SELECT status, error_code FROM promoter_role_backfill_item").fetchone() == ("failed", "system_failure")
    assert database.execute("SELECT status FROM promoter_role_backfill_run").fetchone() == ("failed",)


def test_new_run_reuses_current_result_and_reclassifies_changed_input(database, monkeypatch):
    calls = []

    def classify(event):
        calls.append(event.title)
        return RoleResponse((ProposedRole(1, "both", 1, "8MM"),), ())

    monkeypatch.setattr(backfill, "classify_with_llm", classify)
    first = backfill.create_run(database, (1,), "config")
    database.commit()
    assert backfill.process_run(database, first, "config") == "succeeded"
    second = backfill.create_run(database, (1,), "config")
    database.commit()
    assert backfill.process_run(database, second, "config") == "succeeded"
    assert calls == ["8MM live"]
    database.execute("UPDATE events SET title = '8MM live again' WHERE id = 1")
    database.commit()
    third = backfill.create_run(database, (1,), "config")
    database.commit()
    assert backfill.process_run(database, third, "config") == "succeeded"
    assert calls == ["8MM live", "8MM live again"]


def test_clear_presenter_uses_rules_without_calling_provider(database, monkeypatch):
    database.execute("UPDATE events SET title = '8MM presents' WHERE id = 1")
    database.commit()
    monkeypatch.setattr(backfill, "classify_with_llm", lambda event: pytest.fail("provider should not be called"))
    run_id = backfill.create_run(database, (1,), "config")
    database.commit()
    assert backfill.process_run(database, run_id, "config") == "succeeded"
    assert database.execute("SELECT role, method FROM promoter_event_role").fetchone() == ("both", "rule")


def test_eligibility_excludes_stale_or_removed_roles(database, monkeypatch):
    monkeypatch.setattr(backfill, "classify_with_llm", lambda event: RoleResponse((ProposedRole(1, "organizer", 1, "8MM"),), ()))
    run_id = backfill.create_run(database, (1,), "config")
    database.commit()
    assert backfill.process_run(database, run_id, "config") == "succeeded"
    assert eligible_promoters(database, 1, "config")[0].canonical_id == 1
    assert eligible_promoters(database, 1, "different") == ()
    database.execute("UPDATE events SET title = 'changed' WHERE id = 1")
    assert eligible_promoters(database, 1, "config") == ()
    database.rollback()
    database.execute("DELETE FROM event_promoters WHERE event_id = 1")
    assert eligible_promoters(database, 1, "config") == ()


def test_confirmed_aliases_deduplicate_without_losing_source_ids(database, monkeypatch):
    database.execute("INSERT INTO promoter_identity DEFAULT VALUES")
    database.execute("INSERT INTO promoter_identity_member (promoter_id, identity_id, status, reason, version) VALUES (1, 1, 'confirmed', 'reviewed', 'v1'), (2, 1, 'confirmed', 'reviewed', 'v1')")
    database.execute("INSERT INTO event_promoters VALUES (1, 2)")
    database.commit()
    monkeypatch.setattr(backfill, "classify_with_llm", lambda event: RoleResponse((ProposedRole(1, "organizer", 1, "8MM"), ProposedRole(2, "organizer", 1, "Other")), ()))
    run_id = backfill.create_run(database, (1,), "config")
    database.commit()
    assert backfill.process_run(database, run_id, "config") == "succeeded"
    matches = eligible_promoters(database, 1, "config")
    assert len(matches) == 1
    assert matches[0].canonical_id == 1
    assert matches[0].source_ids == (1, 2)
    rows = database.execute("SELECT promoter_id, source_promoter_ids FROM promoter_role_eligible_links WHERE event_id = 1").fetchall()
    assert rows == [(1, [1, 2])]


def test_sql_eligibility_rejects_changed_event_and_changed_alias(database, monkeypatch):
    monkeypatch.setattr(backfill, "classify_with_llm", lambda event: RoleResponse((ProposedRole(1, "organizer", 1, "8MM"),), ()))
    run_id = backfill.create_run(database, (1,), "config")
    database.commit()
    assert backfill.process_run(database, run_id, "config") == "succeeded"
    assert database.execute("SELECT count(*) FROM promoter_role_eligible_links").fetchone() == (1,)
    database.execute("UPDATE events SET title = 'changed' WHERE id = 1")
    assert database.execute("SELECT count(*) FROM promoter_role_eligible_links").fetchone() == (0,)
    database.rollback()
    database.execute("INSERT INTO promoter_identity DEFAULT VALUES")
    database.execute("INSERT INTO promoter_identity_member (promoter_id, identity_id, status, reason, version) VALUES (1, 1, 'confirmed', 'reviewed', 'v1')")
    assert database.execute("SELECT count(*) FROM promoter_role_eligible_links").fetchone() == (0,)


def test_unknown_and_proposed_aliases_do_not_create_or_merge_credits(database, monkeypatch):
    database.execute("INSERT INTO promoter_identity DEFAULT VALUES")
    database.execute("INSERT INTO promoter_identity_member (promoter_id, identity_id, status, reason, version) VALUES (1, 1, 'proposed', 'unverified', 'v1'), (2, 1, 'proposed', 'unverified', 'v1')")
    database.execute("INSERT INTO event_promoters VALUES (1, 2)")
    database.commit()
    monkeypatch.setattr(backfill, "classify_with_llm", lambda event: RoleResponse((ProposedRole(1, "organizer", 1, "8MM"), ProposedRole(2, "unknown", 0.5, "Other")), ()))
    run_id = backfill.create_run(database, (1,), "config")
    database.commit()
    assert backfill.process_run(database, run_id, "config") == "succeeded"
    matches = eligible_promoters(database, 1, "config")
    assert [(m.canonical_id, m.source_ids) for m in matches] == [(1, (1,))]


def test_enqueue_avoids_duplicate_and_current_events(database, monkeypatch):
    monkeypatch.setattr(backfill, "classify_with_llm", lambda event: RoleResponse((ProposedRole(1, "organizer", 1, "8MM"),), ()))
    first = enqueue_changed_events(database, (1, 1), "config")
    assert len(first) == 1
    assert enqueue_changed_events(database, (1,), "config") == ()
    database.commit()
    assert backfill.process_run(database, first[0], "config") == "succeeded"
    assert enqueue_changed_events(database, (1,), "config") == ()
    database.execute("UPDATE events SET title = 'updated' WHERE id = 1")
    assert len(enqueue_changed_events(database, (1,), "config")) == 1


def test_import_enqueue_uses_ra_ids_and_ingestion_config(database, monkeypatch):
    from types import SimpleNamespace
    from app import promoter_role_queue

    schema = database.execute("SELECT current_schema()").fetchone()[0]
    database.commit()
    monkeypatch.setenv("PGOPTIONS", f"-c search_path={schema}")
    monkeypatch.setattr(promoter_role_queue.EventTagExtractionConfig, "from_env", lambda: SimpleNamespace(provider="kimi_code", model="k3", reasoning_effort="low"))
    runs = enqueue_imported_ra_events(os.environ["DATABASE_URL"], ("ra1", "ra2"))
    assert len(runs) == 1
    assert database.execute("SELECT event_id FROM promoter_role_backfill_item ORDER BY event_id").fetchall() == [(1,), (2,)]
    assert enqueue_imported_ra_events(os.environ["DATABASE_URL"], ("ra1", "ra2")) == ()
