"""Exercise the actual migration against PostgreSQL, rolled back after each test."""

import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from app.promoter_role_llm import OrganizerCandidate, ProposedRole, RoleResponse
from app.promoter_role_store import EventInputChanged, load_event_input, save_llm_roles

@pytest.fixture
def role_db():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for PostgreSQL integration")
    migration = Path(__file__).resolve().parents[1] / "prisma/migrations/20261103000000_promoter_event_roles/migration.sql"
    with psycopg.connect(database_url) as connection:
        schema = "test_promoter_role_" + uuid4().hex
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL("CREATE SCHEMA {} ").format(sql.Identifier(schema)))
                cursor.execute(sql.SQL("SET search_path TO {} ").format(sql.Identifier(schema)))
                cursor.execute("CREATE TABLE events (id BIGINT PRIMARY KEY, title TEXT, description_text TEXT, venue_id BIGINT)")
                cursor.execute("CREATE TABLE promoters (id BIGINT PRIMARY KEY, name TEXT, ra_promoter_id TEXT)")
                cursor.execute("CREATE TABLE venues (id BIGINT PRIMARY KEY, name TEXT)")
                cursor.execute("CREATE TABLE users (id BIGINT PRIMARY KEY)")
                cursor.execute("CREATE TABLE event_promoters (event_id BIGINT, promoter_id BIGINT)")
                cursor.execute(migration.read_text())
                usage_migration = migration.parents[1] / "20261103010000_promoter_role_token_usage/migration.sql"
                cursor.execute(usage_migration.read_text())
                hash_migration = migration.parents[1] / "20261103020000_hash_promoter_role_snapshots/migration.sql"
                cursor.execute(hash_migration.read_text())
                audit_migration = migration.parents[1] / "20261103030000_promoter_identity_audit/migration.sql"
                cursor.execute(audit_migration.read_text())
                shadow_migration = migration.parents[1] / "20261103040000_promoter_shadow_job_identity/migration.sql"
                cursor.execute(shadow_migration.read_text())
                revision_migration = migration.parents[1] / "20261103050000_promoter_role_revision/migration.sql"
                cursor.execute(revision_migration.read_text())
                quality_migration = migration.parents[1] / "20261103060000_promoter_role_quality_gate/migration.sql"
                cursor.execute(quality_migration.read_text())
                integrity_migration = migration.parents[1] / "20261103070000_promoter_role_gate_integrity/migration.sql"
                cursor.execute(integrity_migration.read_text())
                audience_migration = migration.parents[1] / "20261103080000_promoter_role_audience/migration.sql"
                cursor.execute(audience_migration.read_text())
                cursor.execute("INSERT INTO events VALUES (1, '8MM presents', NULL, 1)")
                cursor.execute("INSERT INTO venues VALUES (1, '8MM')")
                cursor.execute("INSERT INTO promoters VALUES (1, '8MM', 'ra1')")
                cursor.execute("INSERT INTO event_promoters VALUES (1, 1)")
                yield cursor
        finally:
            connection.rollback()
            connection.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
            connection.commit()


def test_recreating_ra_relation_preserves_manual_role(role_db):
    role_db.execute("""INSERT INTO promoter_event_role
        (event_id, promoter_id, role, reason_code, method, classifier_version, input_hash)
        VALUES (1, 1, 'both', 'human_review', 'manual', 'v1', 'hash')""")
    role_db.execute("DELETE FROM event_promoters")
    role_db.execute("INSERT INTO event_promoters VALUES (1, 1)")
    role_db.execute("SELECT role, method FROM promoter_event_role")
    assert role_db.fetchone() == ("both", "manual")


def test_invalid_role_is_rejected(role_db):
    with pytest.raises(psycopg.errors.CheckViolation):
        role_db.execute("""INSERT INTO promoter_event_role
            (event_id, promoter_id, role, reason_code, method, classifier_version, input_hash)
            VALUES (1, 1, 'invented', 'test', 'rule', 'v1', 'hash')""")


def test_manual_decision_survives_model_write(role_db):
    role_db.execute("""INSERT INTO promoter_event_role
        (event_id, promoter_id, role, reason_code, method, classifier_version, input_hash)
        VALUES (1, 1, 'both', 'human_review', 'manual', 'v1', 'old')""")
    source = load_event_input(role_db.connection, 1)
    save_llm_roles(role_db.connection, source, RoleResponse((ProposedRole(1, "venue", 0.9, "8MM"),), ()))
    role_db.execute("SELECT role, method, needs_review FROM promoter_event_role")
    assert role_db.fetchone() == ("both", "manual", True)


def test_changed_event_is_not_written(role_db):
    source = load_event_input(role_db.connection, 1)
    role_db.execute("UPDATE events SET title = 'changed' WHERE id = 1")
    with pytest.raises(EventInputChanged):
        save_llm_roles(role_db.connection, source, RoleResponse((ProposedRole(1, "both", 1, "8MM"),), ()))
    role_db.execute("SELECT count(*) FROM promoter_event_role")
    assert role_db.fetchone() == (0,)


def test_text_candidate_suggests_existing_profile_without_confirming(role_db):
    role_db.execute("DELETE FROM event_promoters WHERE event_id = 1")
    source = load_event_input(role_db.connection, 1)
    response = RoleResponse((), (OrganizerCandidate("8MM", 1, "8MM presents"),))
    save_llm_roles(role_db.connection, source, response)
    role_db.execute("SELECT name, status, promoter_id FROM event_organizer_candidate")
    assert role_db.fetchone() == ("8MM", "pending", 1)
    role_db.execute("SELECT count(*) FROM event_promoters")
    assert role_db.fetchone() == (0,)


def test_ambiguous_text_candidate_does_not_choose_profile(role_db):
    role_db.execute("DELETE FROM event_promoters WHERE event_id = 1")
    role_db.execute("INSERT INTO promoters VALUES (2, '8-MM', 'ra2')")
    source = load_event_input(role_db.connection, 1)
    save_llm_roles(role_db.connection, source, RoleResponse((), (OrganizerCandidate("8MM", 1, "8MM presents"),)))
    role_db.execute("SELECT status, promoter_id FROM event_organizer_candidate")
    assert role_db.fetchone() == ("pending", None)
