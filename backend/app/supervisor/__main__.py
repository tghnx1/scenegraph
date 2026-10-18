from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .state import DeterministicSupervisor, JsonStateStore, ProductRunReader
from .telegram import TelegramBotApi, TelegramCommandService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read Scenegraph ingestion supervisor state.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    status = subparsers.add_parser("status")
    status.add_argument("--latest", action="store_true", help="Show the latest persisted import run.")
    details = subparsers.add_parser("details")
    details.add_argument("--run-id", type=int, required=True)
    telegram = subparsers.add_parser("telegram", help="Run the approval-gated Telegram supervisor worker.")
    telegram.add_argument("--once", action="store_true", help="Process currently available updates and exit.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL must be set")
    if args.command == "telegram":
        return run_telegram(database_url, once=args.once)
    state_path = os.environ.get(
        "SUPERVISOR_STATE_PATH",
        str(Path(__file__).resolve().parents[2] / "data/supervisor/state.json"),
    )
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        supervisor = DeterministicSupervisor(
            ProductRunReader(connection),
            JsonStateStore(Path(state_path)),
            telegram=_NoopTelegram(),
        )
        report = supervisor.observe(None if args.command == "status" else args.run_id)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


def run_telegram(database_url: str, *, once: bool) -> int:
    token = os.environ.get("SUPERVISOR_TELEGRAM_BOT_TOKEN", "").strip()
    allowed = tuple(
        value.strip()
        for value in os.environ.get("SUPERVISOR_TELEGRAM_ALLOWED_USER_IDS", "").split(",")
        if value.strip()
    )
    if not token:
        raise SystemExit("SUPERVISOR_TELEGRAM_BOT_TOKEN must be set")
    if not allowed:
        raise SystemExit("SUPERVISOR_TELEGRAM_ALLOWED_USER_IDS must contain at least one user id")
    chat_ids = tuple(
        value.strip()
        for value in os.environ.get("SUPERVISOR_TELEGRAM_CHAT_IDS", "").split(",")
        if value.strip()
    )
    if not chat_ids:
        raise SystemExit("SUPERVISOR_TELEGRAM_CHAT_IDS must contain at least one chat id")
    state_path = os.environ.get(
        "SUPERVISOR_STATE_PATH",
        str(Path(__file__).resolve().parents[2] / "data/supervisor/state.json"),
    )
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        store = JsonStateStore(Path(state_path))
        telegram = TelegramBotApi(token)
        supervisor = DeterministicSupervisor(
            ProductRunReader(connection),
            store,
            telegram=TelegramNotificationSink(telegram, chat_ids),
        )
        service = TelegramCommandService(
            supervisor,
            store,
            telegram,
            allowed_user_ids=allowed,
        )
        if once:
            supervisor.observe()
            service.poll_once(timeout=0)
            return 0
        monitor_interval = max(5.0, float(os.environ.get("SUPERVISOR_MONITOR_INTERVAL_SECONDS", "15")))
        next_monitor = 0.0
        while True:
            try:
                if time.monotonic() >= next_monitor:
                    supervisor.observe()
                    next_monitor = time.monotonic() + monitor_interval
                service.poll_once(timeout=20)
            except Exception:
                # Keep the private worker alive across transient Telegram/DB failures.
                time.sleep(5)


class _NoopTelegram:
    def send(self, _message: str) -> None:
        return None


class TelegramNotificationSink:
    def __init__(self, telegram: TelegramBotApi, chat_ids: tuple[str, ...]) -> None:
        self.telegram = telegram
        self.chat_ids = chat_ids

    def send(self, message: str) -> None:
        for chat_id in self.chat_ids:
            self.telegram.send(message, chat_id=chat_id)


if __name__ == "__main__":
    raise SystemExit(main())
