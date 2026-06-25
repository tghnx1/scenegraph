#!/usr/bin/env python3
"""Load-test the authenticated dashboard page and dashboard API endpoints."""

from __future__ import annotations

import argparse
import json
import os
import ssl
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, build_opener, HTTPSHandler


DEFAULT_BASE_URL = "https://localhost:8443"
DEFAULT_ENV_FILE = Path(".env")
DASHBOARD_API_PATHS = (
    "/api/admin/composition?include=events%2Cartists%2Cpromoters%2Cvenues",
    "/api/admin/metrics",
    "/api/admin/users/pending",
    "/api/admin/users",
    "/api/admin/artist-claims",
    "/api/admin/activity",
)


@dataclass(frozen=True)
class RequestResult:
    """Store one measured HTTP request outcome."""

    label: str
    status: int | None
    seconds: float
    ok: bool
    error: str | None = None
    bytes_read: int = 0


# Load simple KEY=VALUE settings from .env without requiring python-dotenv.
def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


# Prefer process env vars, then .env values, so callers can override credentials safely.
def env_value(name: str, env_file_values: dict[str, str]) -> str:
    value = os.getenv(name) or env_file_values.get(name) or ""
    return value.strip()


# Build an urllib opener that can ignore the local self-signed certificate when requested.
def build_http_opener(insecure: bool):
    if not insecure:
        return build_opener()
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return build_opener(HTTPSHandler(context=context))


# Send JSON login credentials and return the JWT token used by the dashboard API.
def login(base_url: str, username: str, password: str, opener, timeout: float) -> str:
    payload = json.dumps({"username": username, "password": password}).encode("utf-8")
    request = Request(
        urljoin(base_url, "/api/login"),
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    with opener.open(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")

    data = json.loads(body)
    token = data.get("access_token")
    if not data.get("success") or not token:
        message = data.get("message") or data.get("detail") or body
        raise RuntimeError(f"Login failed for {username!r}: {message}")
    return str(token)


# Execute one authenticated GET request and capture timing/status without raising.
def get_once(
    base_url: str,
    path: str,
    token: str,
    opener,
    timeout: float,
    label: str | None = None,
) -> RequestResult:
    started = time.perf_counter()
    request = Request(
        urljoin(base_url, path),
        method="GET",
        headers={"Authorization": f"Bearer {token}", "Accept": "*/*"},
    )

    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read()
            seconds = time.perf_counter() - started
            status = response.getcode()
            return RequestResult(
                label=label or path,
                status=status,
                seconds=seconds,
                ok=200 <= status < 400,
                bytes_read=len(body),
            )
    except HTTPError as error:
        body = error.read()
        seconds = time.perf_counter() - started
        return RequestResult(
            label=label or path,
            status=error.code,
            seconds=seconds,
            ok=False,
            error=f"HTTP {error.code}",
            bytes_read=len(body),
        )
    except (TimeoutError, URLError, OSError) as error:
        seconds = time.perf_counter() - started
        return RequestResult(
            label=label or path,
            status=None,
            seconds=seconds,
            ok=False,
            error=type(error).__name__,
        )


# Simulate one dashboard render by requesting the same admin APIs the frontend loads.
def get_dashboard_api_bundle(
    base_url: str,
    token: str,
    opener,
    timeout: float,
    bundle_index: int,
) -> list[RequestResult]:
    results: list[RequestResult] = []
    for path in DASHBOARD_API_PATHS:
        results.append(
            get_once(
                base_url,
                path,
                token,
                opener,
                timeout,
                label=f"bundle-{bundle_index}:{path}",
            )
        )
    return results


# Calculate percentile using the nearest-rank method to keep output dependency-free.
def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = min(len(sorted_values) - 1, max(0, round((percent / 100) * (len(sorted_values) - 1))))
    return sorted_values[index]


# Print a compact report that is easy to compare between branches.
def print_summary(results: list[RequestResult], wall_seconds: float) -> None:
    durations = [result.seconds for result in results]
    ok_count = sum(1 for result in results if result.ok)
    failed = [result for result in results if not result.ok]
    by_status: dict[str, int] = {}
    by_error: dict[str, int] = {}

    for result in results:
        status_key = str(result.status) if result.status is not None else "no-status"
        by_status[status_key] = by_status.get(status_key, 0) + 1
        if result.error:
            by_error[result.error] = by_error.get(result.error, 0) + 1

    print("\nLoad test summary")
    print("-----------------")
    print(f"total_requests: {len(results)}")
    print(f"successful:     {ok_count}")
    print(f"failed:         {len(failed)}")
    print(f"wall_seconds:   {wall_seconds:.3f}")
    print(f"rps:            {(len(results) / wall_seconds) if wall_seconds else 0:.2f}")
    print(f"status_counts:  {by_status}")
    if by_error:
        print(f"error_counts:   {by_error}")

    if durations:
        print(f"min_seconds:    {min(durations):.3f}")
        print(f"avg_seconds:    {statistics.mean(durations):.3f}")
        print(f"p50_seconds:    {percentile(durations, 50):.3f}")
        print(f"p95_seconds:    {percentile(durations, 95):.3f}")
        print(f"max_seconds:    {max(durations):.3f}")

    if failed:
        print("\nFirst failures")
        print("--------------")
        for result in failed[:10]:
            print(f"{result.label} status={result.status} seconds={result.seconds:.3f} error={result.error}")


# Stream completed futures so failures appear quickly while the load test is running.
def run_load_test(args: argparse.Namespace, token: str, opener) -> list[RequestResult]:
    results: list[RequestResult] = []
    started = time.perf_counter()
    total_tasks = args.requests
    progress_every = max(1, min(args.progress_every, total_tasks))

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        if args.mode == "page":
            futures = [
                executor.submit(
                    get_once,
                    args.base_url,
                    args.path,
                    token,
                    opener,
                    args.request_timeout,
                    f"page-{index}",
                )
                for index in range(args.requests)
            ]
        else:
            futures = [
                executor.submit(
                    get_dashboard_api_bundle,
                    args.base_url,
                    token,
                    opener,
                    args.request_timeout,
                    index,
                )
                for index in range(args.requests)
            ]

        completed_tasks = 0
        for future in as_completed(futures):
            value = future.result()
            if isinstance(value, list):
                results.extend(value)
            else:
                results.append(value)
            completed_tasks += 1
            if completed_tasks == total_tasks or completed_tasks % progress_every == 0:
                elapsed = time.perf_counter() - started
                print(
                    f"progress: {completed_tasks}/{total_tasks} tasks completed, "
                    f"{len(results)} HTTP results collected, elapsed={elapsed:.1f}s",
                    flush=True,
                )

    args.wall_seconds = time.perf_counter() - started
    return results


# Parse CLI arguments so the same script can compare page routing and real API load.
def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("LOAD_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--path", default=os.getenv("LOAD_PATH", "/dashboard"))
    parser.add_argument("--requests", type=int, default=int(os.getenv("LOAD_REQUESTS", "100")))
    parser.add_argument("--concurrency", type=int, default=int(os.getenv("LOAD_CONCURRENCY", "100")))
    parser.add_argument("--progress-every", type=int, default=int(os.getenv("LOAD_PROGRESS_EVERY", "10")))
    parser.add_argument("--request-timeout", type=float, default=float(os.getenv("LOAD_REQUEST_TIMEOUT", "120")))
    parser.add_argument(
        "--mode",
        choices=("page", "dashboard-api"),
        default=os.getenv("LOAD_MODE", "page"),
        help="page = exact GET /dashboard; dashboard-api = frontend dashboard API bundle per request",
    )
    parser.add_argument("--env-file", type=Path, default=Path(os.getenv("LOAD_ENV_FILE", DEFAULT_ENV_FILE)))
    parser.add_argument("--insecure", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args(list(argv))


# Read credentials, authenticate, run the selected load scenario, and print the report.
def main(argv: list[str]) -> int:
    args = parse_args(argv)
    env_file_values = load_env_file(args.env_file)
    username = env_value("BOOTSTRAP_ADMIN_USERNAME", env_file_values)
    password = env_value("BOOTSTRAP_ADMIN_PASSWORD", env_file_values)

    if not username or not password:
        print(
            "BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD must be set in .env or environment",
            file=sys.stderr,
        )
        return 2

    opener = build_http_opener(args.insecure)
    print(f"Logging in as {username!r} at {args.base_url}...")
    try:
        token = login(args.base_url, username, password, opener, args.request_timeout)
    except (RuntimeError, URLError, OSError) as error:
        print(f"Login/connect failed: {error}", file=sys.stderr)
        print("Make sure the stack is running and the admin bootstrap credentials match .env.", file=sys.stderr)
        return 2
    print(
        f"Running mode={args.mode} requests={args.requests} concurrency={args.concurrency} "
        f"target={args.path if args.mode == 'page' else 'dashboard API bundle'}"
    )

    results = run_load_test(args, token, opener)
    print_summary(results, args.wall_seconds)
    return 1 if any(not result.ok for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
