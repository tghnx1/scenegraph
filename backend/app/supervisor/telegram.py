from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from .analysis import analyze_report
from .state import DeterministicSupervisor, JsonStateStore, sanitize


@dataclass(frozen=True)
class TelegramMessage:
    update_id: int
    user_id: str
    chat_id: str
    text: str


@dataclass(frozen=True)
class SupervisorCommand:
    name: str
    argument: str | None = None


ALLOWED_COMMANDS = {"status", "details", "propose", "approve", "reject"}


def parse_command(text: str) -> SupervisorCommand | None:
    parts = text.strip().split()
    if not parts or parts[0].lstrip("/") not in ALLOWED_COMMANDS:
        return None
    name = parts[0].lstrip("/")
    if name == "status" and len(parts) == 1:
        return SupervisorCommand(name)
    if name in {"details", "propose", "approve", "reject"} and len(parts) == 2:
        return SupervisorCommand(name, parts[1])
    return None


class TelegramBotApi:
    """Minimal Telegram transport with no shell or arbitrary HTTP exposure."""

    def __init__(self, token: str, *, api_url: str = "https://api.telegram.org") -> None:
        if not token.strip():
            raise ValueError("Telegram bot token must be configured")
        self._token = token.strip()
        self._api_url = api_url.rstrip("/")

    def _request(self, method: str, values: dict[str, Any]) -> dict[str, Any]:
        encoded = urllib.parse.urlencode(values).encode("utf-8")
        request = urllib.request.Request(
            f"{self._api_url}/bot{self._token}/{method}",
            data=encoded,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram API rejected {method}")
        return payload

    def send(self, message: str, *, chat_id: str) -> None:
        self._request("sendMessage", {"chat_id": chat_id, "text": sanitize(message, limit=3500)})

    def get_updates(self, *, offset: int | None = None, timeout: int = 20) -> list[TelegramMessage]:
        values: dict[str, Any] = {"timeout": max(0, min(timeout, 50))}
        if offset is not None:
            values["offset"] = offset
        payload = self._request("getUpdates", values)
        messages: list[TelegramMessage] = []
        for item in payload.get("result", []):
            message = item.get("message") or {}
            chat = message.get("chat") or {}
            sender = message.get("from") or {}
            text = message.get("text")
            if text is None or chat.get("id") is None or sender.get("id") is None:
                continue
            messages.append(
                TelegramMessage(
                    update_id=int(item["update_id"]),
                    user_id=str(sender["id"]),
                    chat_id=str(chat["id"]),
                    text=sanitize(text, limit=512),
                )
            )
        return messages


class TelegramCommandService:
    def __init__(
        self,
        supervisor: DeterministicSupervisor,
        store: JsonStateStore,
        telegram: TelegramBotApi,
        *,
        allowed_user_ids: Iterable[str],
    ) -> None:
        self.supervisor = supervisor
        self.store = store
        self.telegram = telegram
        self.allowed_user_ids = {str(value) for value in allowed_user_ids}

    def handle(self, message: TelegramMessage) -> str:
        if message.user_id not in self.allowed_user_ids:
            return "unauthorized"
        command = parse_command(message.text)
        if command is None:
            return "command_not_allowed"
        if command.name == "status":
            report = self.supervisor.observe()
            response = json.dumps({"run_id": report["run_id"], "status": report["status"], "progress": report["progress"]}, sort_keys=True)
        elif command.name == "details":
            response = self._details(command.argument or "")
        elif command.name == "propose":
            response = self._propose(command.argument or "")
        else:
            response = self._resolve_action(command.name, command.argument or "")
        self.telegram.send(response, chat_id=message.chat_id)
        return response

    def _propose(self, run_id: str) -> str:
        try:
            report = self.supervisor.observe(int(run_id))
        except (TypeError, ValueError):
            return "invalid_run_id"
        state = self.store.load()
        actions = state.setdefault("actions", {})
        action_id = f"action-{len(actions) + 1}"
        created_at = datetime.now(timezone.utc)
        actions[action_id] = {
            "id": action_id,
            "type": "review_run",
            "run_id": report["run_id"],
            "analysis": analyze_report(report),
            "status": "pending",
            "created_at": created_at.isoformat(),
            "expires_at": (created_at + timedelta(hours=1)).isoformat(),
        }
        self.store.save(state)
        return f"Proposed {action_id}; explicit approval is required."

    def _details(self, run_id: str) -> str:
        try:
            report = self.supervisor.observe(int(run_id))
        except (TypeError, ValueError):
            return "invalid_run_id"
        return json.dumps(
            {"run_id": report["run_id"], "stages": report["stages"], "analysis": analyze_report(report)},
            sort_keys=True,
        )

    def poll_once(self, *, timeout: int = 0) -> int:
        """Process each Telegram update once, persisting the next offset."""
        state = self.store.load()
        offset = state.get("telegram", {}).get("next_update_id")
        messages = self.telegram.get_updates(offset=offset, timeout=timeout)
        for message in messages:
            self.handle(message)
            state = self.store.load()
            state.setdefault("telegram", {})["next_update_id"] = message.update_id + 1
            self.store.save(state)
        return len(messages)

    def _resolve_action(self, command: str, action_id: str) -> str:
        state = self.store.load()
        action = state.get("actions", {}).get(action_id)
        if action is None:
            return "unknown_action"
        if action.get("status") in {"approved", "rejected"}:
            return str(action["status"])
        try:
            expired = datetime.now(timezone.utc) >= datetime.fromisoformat(str(action["expires_at"]))
        except (KeyError, TypeError, ValueError):
            expired = True
        if expired:
            action["status"] = "expired"
            self.store.save(state)
            return "expired"
        action["status"] = "approved" if command == "approve" else "rejected"
        self.store.save(state)
        return str(action["status"])
