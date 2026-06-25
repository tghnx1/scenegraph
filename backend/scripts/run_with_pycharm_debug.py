"""Start the backend under a PyCharm Debug Server connection.

This script is used only in the debug Docker compose override. It connects the
backend process back to the PyCharm debug server that is already waiting on the
host machine, then starts Uvicorn.
"""

from __future__ import annotations

import os
import sys

import uvicorn


def connect_to_pycharm_debug_server() -> None:
    """Attach the current process to the PyCharm debug server."""

    debug_host = os.getenv("PYCHARM_DEBUG_HOST", "host.docker.internal")
    debug_port = int(os.getenv("PYCHARM_DEBUG_PORT", "5678"))
    suspend = os.getenv("PYCHARM_DEBUG_SUSPEND", "1").strip().lower() not in {
        "0",
        "false",
        "no",
    }

    try:
        import pydevd_pycharm
    except ImportError as exc:  # pragma: no cover - startup guard
        raise RuntimeError(
            "pydevd-pycharm is required for the PyCharm debug stack"
        ) from exc

    pydevd_pycharm.settrace(
        debug_host,
        port=debug_port,
        stdoutToServer=True,
        stderrToServer=True,
        suspend=suspend,
    )


def main() -> None:
    """Connect to PyCharm and launch the API server."""

    connect_to_pycharm_debug_server()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=3000,
    )


if __name__ == "__main__":
    sys.exit(main())
