"""Review and explicitly confirm or undo promoter identity memberships."""

from __future__ import annotations

import argparse
import json
import os

import psycopg

from app.promoter_role_identity import confirm_profiles, unconfirm_profile


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--confirm", type=int, action="append", help="Internal promoter ID; supply at least two")
    action.add_argument("--unconfirm", type=int, help="Internal promoter ID")
    parser.add_argument("--reason", help="Short review basis; never include credentials")
    parser.add_argument("--apply", action="store_true", help="Persist the explicit review decision")
    args = parser.parse_args()
    if args.confirm and (len(args.confirm) < 2 or len(args.confirm) != len(set(args.confirm))):
        parser.error("--confirm requires at least two unique profile IDs")
    if args.apply and not args.reason:
        parser.error("--apply requires --reason")
    ids = args.confirm if args.confirm else [args.unconfirm]
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        if not args.apply:
            connection.execute("SET TRANSACTION READ ONLY")
        rows = connection.execute("""
            SELECT p.id, p.ra_promoter_id, p.name, m.identity_id, m.status
            FROM promoters p LEFT JOIN promoter_identity_member m ON m.promoter_id = p.id
            WHERE p.id = ANY(%s) ORDER BY p.id
        """, (ids,)).fetchall()
        if len(rows) != len(ids):
            raise SystemExit("one or more profiles do not exist")
        result = {"profiles": rows, "applied": args.apply}
        if args.apply:
            if args.confirm:
                result["confirmed_identity"] = confirm_profiles(connection, tuple(args.confirm), args.reason)
            else:
                unconfirm_profile(connection, args.unconfirm, args.reason)
                result["membership"] = "proposed"
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
