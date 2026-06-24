from __future__ import annotations

import argparse
import json
import time

from app.db import get_connection


# Measure repeated short checkouts so we can compare pooled vs non-pooled checkout cost.
def benchmark(iterations: int) -> dict[str, object]:
    """Run repeated connection checkouts and summarize elapsed time and backend PIDs."""
    backend_pids: list[int] = []
    checkout_ids: list[int] = []

    start = time.perf_counter()
    for _ in range(iterations):
        with get_connection() as connection:
            backend_pid = getattr(getattr(connection, "info", None), "backend_pid", None)
            if backend_pid is not None:
                backend_pids.append(int(backend_pid))
            checkout_ids.append(id(connection))
    elapsed = time.perf_counter() - start

    return {
        "iterations": iterations,
        "elapsedSeconds": elapsed,
        "averageMsPerCheckout": (elapsed / iterations) * 1000.0 if iterations else 0.0,
        "uniqueBackendPids": len(set(backend_pids)),
        "backendPids": backend_pids[:10],
        "uniqueCheckoutObjectIds": len(set(checkout_ids)),
    }


def main() -> None:
    """Print a compact JSON benchmark result for connection checkout reuse."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=20)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.iterations), indent=2))


if __name__ == "__main__":
    main()
