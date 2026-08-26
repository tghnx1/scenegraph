#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the live Scenegraph health response.")
    parser.add_argument("--url", default="https://scenematch.dev/health")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--retry-seconds", type=float, default=5.0)
    return parser.parse_args()


def validate_health_payload(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["response is not a JSON object"]

    errors: list[str] = []
    if payload.get("status") != "ok":
        errors.append(f"status={payload.get('status')!r}, expected 'ok'")
    if payload.get("database") != "ok":
        errors.append(f"database={payload.get('database')!r}, expected 'ok'")

    schema = payload.get("schema")
    if not isinstance(schema, dict):
        errors.append("schema is not an object")
        return errors
    if schema.get("status") != "ok":
        errors.append(f"schema.status={schema.get('status')!r}, expected 'ok'")
    missing_tables = schema.get("missingRequiredTables")
    if missing_tables != []:
        errors.append(
            f"schema.missingRequiredTables={missing_tables!r}, expected []"
        )
    return errors


def fetch_health(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Scenegraph-Production-Smoke/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status}")
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"request failed: {exc.reason}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("response was not valid JSON") from exc


def wait_for_healthy(url: str, timeout_seconds: int, retry_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    attempt = 0
    last_error = "health check did not run"
    while True:
        attempt += 1
        try:
            errors = validate_health_payload(fetch_health(url))
            if not errors:
                print(
                    "Production health passed: HTTP 200, status=ok, database=ok, "
                    "schema.status=ok, missingRequiredTables=[]"
                )
                return
            last_error = "; ".join(errors)
        except RuntimeError as exc:
            last_error = str(exc)

        print(f"Production health attempt {attempt} not ready: {last_error}")
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"production health did not pass within {timeout_seconds} seconds: "
                f"{last_error}"
            )
        time.sleep(retry_seconds)


def main() -> int:
    args = parse_args()
    try:
        wait_for_healthy(args.url, args.timeout_seconds, args.retry_seconds)
    except TimeoutError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
