from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def load_script(name: str, filename: str):
    path = REPO_ROOT / "scripts" / filename
    if not path.exists():
        pytest.skip(f"repository scripts are not mounted in this backend container: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_coolify_deploy_extracts_current_api_deployment_uuid():
    module = load_script("coolify_deploy_contract", "coolify_deploy.py")

    assert module.extract_deployment_uuid(
        {
            "deployments": [
                {
                    "message": "Deployment request queued.",
                    "resource_uuid": "app-1",
                    "deployment_uuid": "deployment-1",
                }
            ]
        }
    ) == "deployment-1"


def test_coolify_deploy_rejects_response_without_identifier():
    module = load_script("coolify_deploy_missing_id", "coolify_deploy.py")

    with pytest.raises(ValueError, match="deployment_uuid"):
        module.extract_deployment_uuid({"message": "queued"})


@pytest.mark.parametrize("status", ["finished", " FINISHED "])
def test_coolify_finished_status_normalizes_as_success(status):
    module = load_script("coolify_deploy_status", "coolify_deploy.py")

    assert module.normalize_status(status) in module.SUCCESS_STATUSES


@pytest.mark.parametrize("status", ["failed", "cancelled", "cancelled-by-user"])
def test_coolify_failure_statuses_are_terminal(status):
    module = load_script(f"coolify_deploy_{status}", "coolify_deploy.py")

    assert module.normalize_status(status) in module.FAILURE_STATUSES


def test_production_health_requires_database_and_clean_schema():
    module = load_script("production_smoke_valid", "production_smoke_test.py")

    assert module.validate_health_payload(
        {
            "status": "ok",
            "database": "ok",
            "schema": {"status": "ok", "missingRequiredTables": []},
        }
    ) == []


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "error", "database": "ok", "schema": {"status": "ok", "missingRequiredTables": []}},
        {"status": "ok", "database": "error", "schema": {"status": "ok", "missingRequiredTables": []}},
        {"status": "ok", "database": "ok", "schema": {"status": "degraded", "missingRequiredTables": []}},
        {"status": "ok", "database": "ok", "schema": {"status": "ok", "missingRequiredTables": ["users"]}},
    ],
)
def test_production_health_rejects_partial_success(payload):
    module = load_script("production_smoke_invalid", "production_smoke_test.py")

    assert module.validate_health_payload(payload)


def test_pgvector_migration_uses_indexable_embedding_dimensions():
    migration = (
        REPO_ROOT
        / "backend"
        / "prisma"
        / "migrations"
        / "20260527101000_add_pgvector_embedding_vec"
        / "migration.sql"
    ).read_text()

    assert "embedding_vec vector(1536)" in migration
    assert "AND dimensions = 1536" in migration


def test_ci_seed_provides_expected_recommendation_graph_contract():
    seed = (REPO_ROOT / "backend" / "tests" / "ci_seed.py").read_text()

    assert "(2178, 'ci-source-artist'" in seed
    assert "(2179, 'ci-connected-artist'" in seed
    assert "(2180, 'ci-semantic-artist'" in seed
    assert "(9800001, 2178)" in seed
    assert "(9800001, 2179)" in seed
    assert "(9800002, 2179)" in seed
    assert "(9800002, 9700001)" in seed
    assert "(9800003, 9700002)" in seed
    assert "'openai:text-embedding-3-small'" in seed
    assert "array_fill(0.01::real, ARRAY[1536])::vector" in seed
