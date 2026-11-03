"""Inspect or explicitly revoke a recorded promoter-role quality review."""

from __future__ import annotations

import argparse
import json
import os

import psycopg

from app.promoter_role_evaluation_db import revoke_quality_review


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-id", type=int, required=True)
    parser.add_argument("--reason")
    parser.add_argument("--apply", action="store_true", help="Append a revocation")
    args = parser.parse_args()
    if args.apply and not args.reason:
        parser.error("--apply requires --reason")
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        if not args.apply:
            connection.execute("SET TRANSACTION READ ONLY")
        row = connection.execute("""
            SELECT r.id, r.classifier_version, r.config_hash,
                   EXISTS(SELECT 1 FROM promoter_role_quality_revocation x WHERE x.review_id = r.id)
            FROM promoter_role_quality_review r WHERE r.id = %s
        """, (args.review_id,)).fetchone()
        if row is None:
            raise SystemExit("review not found")
        if args.apply:
            revoke_quality_review(connection, args.review_id, args.reason)
    print(json.dumps({"review_id": row[0], "classifier_version": row[1], "config_hash": row[2],
                      "previously_revoked": row[3], "revoked": args.apply or row[3]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
