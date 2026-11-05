"""Resolve gated promoter-role mode and cache revision for one user."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from psycopg import Connection
from psycopg.rows import tuple_row

from app.promoter_roles import CLASSIFIER_VERSION


class RoleRuntimeConfigurationError(RuntimeError):
    """An enabled role mode has no matching valid runtime configuration."""


@dataclass(frozen=True, slots=True)
class RoleRuntimeContext:
    mode: Literal["off", "enforce"]
    revision: int
    config_hash: str | None


def resolve_runtime_context(connection: Connection, *, user_id: int,
                            current_config_hash: str | None = None, lock: bool = False) -> RoleRuntimeContext:
    """Resolve only approved and allowlisted mode; lock the revision when committing a result."""
    with connection.cursor(row_factory=tuple_row) as cursor:
        cursor.execute("""
            SELECT s.enabled, s.revision, s.audience, s.config_hash, s.classifier_version,
              EXISTS (SELECT 1 FROM promoter_role_allowlist a WHERE a.user_id = %s),
              EXISTS (SELECT 1 FROM promoter_role_quality_review q
                WHERE q.id = s.quality_review_id AND q.config_hash = s.config_hash
                  AND q.classifier_version = s.classifier_version
                  AND NOT EXISTS (SELECT 1 FROM promoter_role_quality_revocation x WHERE x.review_id = q.id))
            FROM promoter_role_runtime_state s WHERE s.id = 1
        """ + (" FOR SHARE OF s" if lock else ""), (user_id,))
        row = cursor.fetchone()
    if row is None:
        raise RoleRuntimeConfigurationError("promoter role runtime state is missing")
    enabled, revision, audience, stored_hash, version, allowed, review_valid = row
    if not enabled or (audience == "allowlist" and not allowed):
        return RoleRuntimeContext("off", int(revision), None)
    if current_config_hash is None:
        from app.event_tag_extraction import EventTagExtractionConfig
        from app.promoter_role_backfill import extraction_config_hash

        try:
            current_config_hash = extraction_config_hash(EventTagExtractionConfig.from_env())
        except (KeyError, ValueError) as error:
            raise RoleRuntimeConfigurationError("promoter role extraction configuration is unavailable") from error
    if audience not in {"all", "allowlist"} or not review_valid or version != CLASSIFIER_VERSION or not current_config_hash or stored_hash != current_config_hash:
        raise RoleRuntimeConfigurationError("promoter role runtime does not match its approved configuration")
    return RoleRuntimeContext("enforce", int(revision), stored_hash)
