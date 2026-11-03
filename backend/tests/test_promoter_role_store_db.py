"""Exercise the actual migration against PostgreSQL, rolled back after each test."""

import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from app.promoter_role_llm import ProposedRole, RoleResponse
from app.promoter_role_store import EventInputChanged, load_event_input, save_llm_roles

@pytest.fixture
def role_db():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for PostgreSQL integration")
    migration = Path(__file__).resolve().parents[1] / "prisma/migrations/20261103000000_promoter_event_roles/migration.sql"
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            schema = "test_promoter_role_" + uuid4().hex
            cursor.execute(sql.SQL("CREATE SCHEMA {} ").format(sql.Identifier(schema)))
            cursor.execute(sql.SQL("SET LOCAL search_path TO {} ").format(sql.Identifier(schema)))
            cursor.execute("CREATE TABLE events (id BIGINT PRIMARY KEY, title TEXT, description_text TEXT, venue_id BIGINT)")
            cursor.execute("CREATE TABLE promoters (id BIGINT PRIMARY KEY, name TEXT)")
            cursor.execute("CREATE TABLE venues (id BIGINT PRIMARY KEY, name TEXT)")
            cursor.execute("CREATE TABLE event_promoters (event_id BIGINT, promoter_id BIGINT)")
            cursor.execute(migration.read_text())
            usage_migration = migration.parents[1] / "20261103010000_promoter_role_token_usage/migration.sql"
            cursor.execute(usage_migration.read_text())
            cursor.execute("INSERT INTO events VALUES (1, '8MM presents', NULL, 1)")
            cursor.execute("INSERT INTO venues VALUES (1, '8MM')")
            cursor.execute("INSERT INTO promoters VALUES (1, '8MM')")
            cursor.execute("INSERT INTO event_promoters VALUES (1, 1)")
            yield cursor
        connection.rollback()


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
