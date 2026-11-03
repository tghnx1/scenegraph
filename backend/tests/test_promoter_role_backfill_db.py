"""Run durable backfill transitions against a real PostgreSQL schema."""

import os
import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import httpx
from openai import PermissionDeniedError, RateLimitError
from psycopg import sql

from app import promoter_role_backfill as backfill
from app.promoter_role_llm import ProposedRole, RoleResponse
from app.promoter_role_eligibility import eligible_promoters
from app.promoter_role_queue import enqueue_changed_events, enqueue_imported_ra_events
from app.promoter_role_relation import role_filtered_relation
from app.promoter_role_shadow import compare_recommendations
from app.promoter_role_candidates import find_candidate_matches
from app.promoter_role_worker import process_next
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
            connection.execute("CREATE TABLE promoters (id BIGINT PRIMARY KEY, name TEXT, ra_promoter_id TEXT)")
            connection.execute("CREATE TABLE venues (id BIGINT PRIMARY KEY, name TEXT)")
            connection.execute("CREATE TABLE event_promoters (event_id BIGINT, promoter_id BIGINT)")
            connection.execute(migration.read_text())
            usage_migration = migration.parents[1] / "20261103010000_promoter_role_token_usage/migration.sql"
            connection.execute(usage_migration.read_text())
            hash_migration = migration.parents[1] / "20261103020000_hash_promoter_role_snapshots/migration.sql"
            connection.execute(hash_migration.read_text())
            connection.execute("INSERT INTO events VALUES (1, '8MM live', NULL, 1, 'ra1'), (2, 'Other live', NULL, NULL, 'ra2')")
            connection.execute("INSERT INTO venues VALUES (1, '8MM')")
            connection.execute("INSERT INTO promoters VALUES (1, '8MM', 'ra1'), (2, 'Other', 'ra2')")
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


def test_config_hash_changes_with_provider_endpoint(monkeypatch):
    from types import SimpleNamespace

    config = SimpleNamespace(provider="kimi_code", model="k3", reasoning_effort="low")
    monkeypatch.setenv("KIMI_BASE_URL", "https://one.example/v1")
    original = backfill.extraction_config_hash(config)
    monkeypatch.setenv("KIMI_BASE_URL", "https://two.example/v1")
    assert backfill.extraction_config_hash(config) != original


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


@pytest.mark.parametrize("error_type,message,expected", [
    ("access_terminated_error", "You've reached your 5-hour usage limit", "paused"),
    ("access_terminated_error", "Account terminated for policy reasons", "failed"),
    ("permission_denied", "Access denied", "failed"),
])
def test_403_is_quota_only_when_explicit(database, monkeypatch, error_type, message, expected):
    response = httpx.Response(403, request=httpx.Request("POST", "https://example.invalid"))

    def deny(_event):
        raise PermissionDeniedError("provider error", response=response, body={"type": error_type, "message": message})

    monkeypatch.setattr(backfill, "classify_with_llm", deny)
    run_id = backfill.create_run(database, (1,), "config")
    database.commit()
    assert backfill.process_run(database, run_id, "config") == expected
    row = database.execute("SELECT status, attempts, error_code FROM promoter_role_backfill_item").fetchone()
    if expected == "paused":
        assert row == ("pending", 0, "provider_quota")
    else:
        assert row == ("failed", 1, "provider_system_failure")


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


def test_status_command_only_reads_persisted_state(database):
    schema = database.execute("SELECT current_schema()").fetchone()[0]
    run_id = backfill.create_run(database, (1,), "config")
    database.commit()
    env = os.environ.copy()
    env["PGOPTIONS"] = f"-c search_path={schema}"
    result = subprocess.run([sys.executable, "-m", "app.promoter_role_backfill_cli", "--status-run", str(run_id)],
                            env=env, capture_output=True, text=True, check=True)
    status = json.loads(result.stdout)
    assert status["status"] == "queued"
    assert status["items"] == {"pending": 1}
    assert status["reported_input_tokens"] is None
    assert database.execute("SELECT status FROM promoter_role_backfill_run").fetchone() == ("queued",)


def test_status_command_serializes_nonempty_token_totals(database):
    schema = database.execute("SELECT current_schema()").fetchone()[0]
    run_id = backfill.create_run(database, (1,), "config")
    database.execute("UPDATE promoter_role_backfill_item SET input_tokens = 123, output_tokens = 45 WHERE run_id = %s", (run_id,))
    database.commit()
    env = os.environ.copy()
    env["PGOPTIONS"] = f"-c search_path={schema}"
    result = subprocess.run([sys.executable, "-m", "app.promoter_role_backfill_cli", "--status-run", str(run_id)],
                            env=env, capture_output=True, text=True, check=True)
    status = json.loads(result.stdout)
    assert status["reported_input_tokens"] == 123
    assert status["reported_output_tokens"] == 45


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


def test_provider_usage_is_persisted_with_the_event(database, monkeypatch):
    monkeypatch.setattr(backfill, "classify_with_llm", lambda event: RoleResponse((ProposedRole(1, "organizer", 1, "8MM"),), (), 123, 45))
    run_id = backfill.create_run(database, (1,), "config")
    database.commit()
    assert backfill.process_run(database, run_id, "config") == "succeeded"
    assert database.execute("SELECT input_tokens, output_tokens FROM promoter_role_backfill_item").fetchone() == (123, 45)


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
    snapshot = database.execute("SELECT input_snapshot FROM promoter_event_classification").fetchone()[0]
    assert "8MM live" not in json.dumps(snapshot)
    assert "8MM" not in json.dumps(snapshot)
    assert database.execute("SELECT count(*) FROM promoter_role_eligible_links").fetchone() == (1,)
    database.execute("UPDATE events SET title = 'changed' WHERE id = 1")
    assert database.execute("SELECT count(*) FROM promoter_role_eligible_links").fetchone() == (0,)
    database.rollback()
    database.execute("INSERT INTO promoter_identity DEFAULT VALUES")
    database.execute("INSERT INTO promoter_identity_member (promoter_id, identity_id, status, reason, version) VALUES (1, 1, 'confirmed', 'reviewed', 'v1')")
    assert database.execute("SELECT count(*) FROM promoter_role_eligible_links").fetchone() == (0,)


def test_snapshot_migration_preserves_existing_eligibility(database, monkeypatch):
    from psycopg.types.json import Jsonb

    monkeypatch.setattr(backfill, "classify_with_llm", lambda event: RoleResponse((ProposedRole(1, "organizer", 1, "8MM"),), ()))
    run_id = backfill.create_run(database, (1,), "config")
    database.commit()
    assert backfill.process_run(database, run_id, "config") == "succeeded"
    old_snapshot = {"event_id": 1, "title": "8MM live", "description": "", "venue_id": 1,
                    "venue_name": "8MM", "promoters": [{"id": 1, "name": "8MM", "identity_id": None}]}
    database.execute("UPDATE promoter_event_classification SET input_snapshot = %s", (Jsonb(old_snapshot),))
    migration = Path(__file__).resolve().parents[1] / "prisma/migrations/20261103020000_hash_promoter_role_snapshots/migration.sql"
    database.execute(migration.read_text())
    snapshot = database.execute("SELECT input_snapshot FROM promoter_event_classification").fetchone()[0]
    assert "8MM" not in json.dumps(snapshot)
    assert database.execute("SELECT count(*) FROM promoter_role_eligible_links").fetchone() == (1,)


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


def test_worker_processes_only_queued_compatible_runs(database, monkeypatch):
    database.execute("UPDATE events SET title = '8MM presents' WHERE id = 1")
    run_id = backfill.create_run(database, (1,), "config")
    database.commit()
    monkeypatch.setattr(backfill, "classify_with_llm", lambda event: pytest.fail("rule should avoid the provider"))
    assert process_next(database, "different") is None
    assert process_next(database, "config") == "succeeded"
    assert process_next(database, "config") is None
    assert database.execute("SELECT status FROM promoter_role_backfill_run WHERE id = %s", (run_id,)).fetchone() == ("succeeded",)


def test_filtered_relation_is_scoped_and_preserves_ra_data(database, monkeypatch):
    monkeypatch.setattr(backfill, "classify_with_llm", lambda event: RoleResponse((ProposedRole(1, "organizer", 1, "8MM"),), ()))
    run_id = backfill.create_run(database, (1,), "config")
    database.commit()
    assert backfill.process_run(database, run_id, "config") == "succeeded"
    assert database.execute("SELECT count(*) FROM event_promoters").fetchone() == (2,)
    with role_filtered_relation(database, "config"):
        assert database.execute("SELECT event_id, promoter_id FROM event_promoters").fetchall() == [(1, 1)]
    assert database.execute("SELECT count(*) FROM event_promoters").fetchone() == (2,)


def test_filtered_relation_rolls_back_when_query_fails(database):
    with pytest.raises(psycopg.errors.DivisionByZero):
        with role_filtered_relation(database, "config"):
            database.execute("SELECT 1 / 0")
    assert database.execute("SELECT count(*) FROM event_promoters").fetchone() == (2,)


def test_shadow_compares_real_relation_without_changing_base(database, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(backfill, "classify_with_llm", lambda event: RoleResponse((ProposedRole(1, "organizer", 1, "8MM"),), ()))
    run_id = backfill.create_run(database, (1,), "config")
    database.commit()
    assert backfill.process_run(database, run_id, "config") == "succeeded"

    def builder(connection, **kwargs):
        ids = connection.execute("SELECT promoter_id FROM event_promoters ORDER BY promoter_id").fetchall()
        return SimpleNamespace(recommendations=[SimpleNamespace(id=row[0]) for row in ids])

    result = compare_recommendations(database, artist_id=1, user_id=1, limit=10,
                                     current_config_hash="config", builder=builder)
    assert result.baseline_ids == (1, 2)
    assert result.shadow_ids == (1,)
    assert result.removed_ids == (2,)
    assert database.execute("SELECT count(*) FROM event_promoters").fetchone() == (2,)
    assert database.execute("SELECT count(*) FROM promoter_role_shadow_result").fetchone() == (0,)


def test_candidate_matches_remain_proposals_and_preserve_ra_ids(database):
    database.execute("INSERT INTO promoters VALUES (3, '8-MM', 'ra3')")
    matches = find_candidate_matches(database, '8 MM')
    assert [(item.promoter_id, item.ra_promoter_id) for item in matches] == [(1, 'ra1'), (3, 'ra3')]
    assert all(item.confirmed_identity_id is None for item in matches)
    assert database.execute("SELECT count(*) FROM event_organizer_candidate").fetchone() == (0,)


def test_role_readers_accept_application_dict_row_connections(database):
    from psycopg.rows import dict_row
    from app.promoter_role_store import load_event_input

    database.row_factory = dict_row
    try:
        assert load_event_input(database, 1).title == "8MM live"
        assert find_candidate_matches(database, "8MM")[0].ra_promoter_id == "ra1"
        assert eligible_promoters(database, 1, "config") == ()
    finally:
        database.row_factory = psycopg.rows.tuple_row
