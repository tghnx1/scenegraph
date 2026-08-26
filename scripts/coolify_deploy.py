#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


SUCCESS_STATUSES = {"finished"}
FAILURE_STATUSES = {
    "cancelled",
    "cancelled-by-user",
    "cancelled_by_user",
    "failed",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trigger and wait for a Coolify deployment.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--application-uuid", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--poll-seconds", type=float, default=8.0)
    return parser.parse_args()


def extract_deployment_uuid(payload: Any) -> str:
    candidates: list[Any] = []
    if isinstance(payload, dict):
        candidates.append(payload)
        deployments = payload.get("deployments")
        if isinstance(deployments, list):
            candidates.extend(deployments)

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        value = candidate.get("deployment_uuid")
        if isinstance(value, str) and value.strip():
            return value.strip()

    raise ValueError("Coolify response did not contain a deployment_uuid")


def normalize_status(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Coolify deployment response did not contain a status")
    return value.strip().lower()


def request_json(
    url: str,
    token: str,
    *,
    method: str = "GET",
    timeout: float = 30.0,
) -> Any:
    request = urllib.request.Request(
        url,
        method=method,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"Coolify returned HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Coolify returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Coolify request failed: {exc.reason}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Coolify returned invalid JSON") from exc


def deploy_and_wait(
    *,
    base_url: str,
    application_uuid: str,
    token: str,
    timeout_seconds: int,
    poll_seconds: float,
) -> str:
    api_url = base_url.rstrip("/") + "/api/v1"
    query = urllib.parse.urlencode(
        {"uuid": application_uuid, "force": "false"}
    )
    payload = request_json(f"{api_url}/deploy?{query}", token, method="POST")
    deployment_uuid = extract_deployment_uuid(payload)
    print("Coolify deploy accepted")
    print(f"Coolify deployment ID: {deployment_uuid}")

    deployment_url = f"{api_url}/deployments/{urllib.parse.quote(deployment_uuid, safe='')}"
    deadline = time.monotonic() + timeout_seconds
    previous_status: str | None = None

    while True:
        status_payload = request_json(deployment_url, token)
        if not isinstance(status_payload, dict):
            raise RuntimeError("Coolify deployment status response was not an object")
        status = normalize_status(status_payload.get("status"))
        if status != previous_status:
            print(f"Coolify deployment status: {status}")
            previous_status = status

        if status in SUCCESS_STATUSES:
            print(f"Coolify deployment completed successfully: {deployment_uuid}")
            return deployment_uuid
        if status in FAILURE_STATUSES:
            raise RuntimeError(
                f"Coolify deployment {deployment_uuid} ended with status {status}"
            )
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Coolify deployment {deployment_uuid} did not finish within "
                f"{timeout_seconds} seconds; last status: {status}"
            )
        time.sleep(poll_seconds)


def main() -> int:
    args = parse_args()
    token = os.environ.get("COOLIFY_DEPLOY_TOKEN", "").strip()
    if not token:
        print("COOLIFY_DEPLOY_TOKEN must be set", file=sys.stderr)
        return 2

    try:
        deploy_and_wait(
            base_url=args.base_url,
            application_uuid=args.application_uuid,
            token=token,
            timeout_seconds=args.timeout_seconds,
            poll_seconds=args.poll_seconds,
        )
    except (RuntimeError, TimeoutError, ValueError) as exc:
        print(f"Coolify deployment failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
