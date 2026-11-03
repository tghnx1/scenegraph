"""Inspect and control the reviewed, user-scoped promoter-role rollout."""

from __future__ import annotations

import argparse
import json
import os

import psycopg
from psycopg.rows import dict_row

from app.event_tag_extraction import EventTagExtractionConfig
from app.promoter_role_backfill import extraction_config_hash
from app.promoter_roles import CLASSIFIER_VERSION


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--status", action="store_true")
    operation.add_argument("--enable-review", type=int, metavar="ID")
    operation.add_argument("--disable", action="store_true")
    operation.add_argument("--add-user", type=int, metavar="ID")
    operation.add_argument("--remove-user", type=int, metavar="ID")
    operation.add_argument("--audience", choices=("allowlist", "all"))
    parser.add_argument("--apply", action="store_true", help="Persist the change; without this flag roll it back")
    args = parser.parse_args()
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as connection:
        if args.enable_review is not None:
            current_hash = extraction_config_hash(EventTagExtractionConfig.from_env())
            review = connection.execute("""SELECT config_hash, classifier_version FROM promoter_role_quality_review
                WHERE id = %s AND NOT EXISTS
                (SELECT 1 FROM promoter_role_quality_revocation WHERE review_id = %s)""",
                (args.enable_review, args.enable_review)).fetchone()
            if not review or review["config_hash"] != current_hash or review["classifier_version"] != CLASSIFIER_VERSION:
                raise ValueError("Review is unavailable, revoked, or does not match current configuration")
            connection.execute("""UPDATE promoter_role_runtime_state SET enabled = true, quality_review_id = %s,
                config_hash = %s, classifier_version = %s WHERE id = 1""",
                (args.enable_review, current_hash, CLASSIFIER_VERSION))
        elif args.disable:
            connection.execute("UPDATE promoter_role_runtime_state SET enabled = false WHERE id = 1")
        elif args.add_user is not None:
            connection.execute("INSERT INTO promoter_role_allowlist (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (args.add_user,))
        elif args.remove_user is not None:
            connection.execute("DELETE FROM promoter_role_allowlist WHERE user_id = %s", (args.remove_user,))
        elif args.audience:
            connection.execute("UPDATE promoter_role_runtime_state SET audience = %s WHERE id = 1", (args.audience,))
        state = connection.execute("""SELECT enabled, audience, revision, quality_review_id, classifier_version
            FROM promoter_role_runtime_state WHERE id = 1""").fetchone()
        users = [row["user_id"] for row in connection.execute("SELECT user_id FROM promoter_role_allowlist ORDER BY user_id")]
        print(json.dumps({"state": state, "user_ids": users, "persisted": bool(args.apply and not args.status)}))
        if args.apply and not args.status:
            connection.commit()
        else:
            connection.rollback()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
