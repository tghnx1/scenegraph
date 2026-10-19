from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Any, Iterable

from .analysis import analyze_report, explain_report
from .actions import ApprovedActionExecutor
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
RETRY_ACTION_RE = re.compile(r"^retry_quarantine:(artist|event):([1-9][0-9]*):([a-z0-9_-]+)$")


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
        action_executor: ApprovedActionExecutor | None = None,
        analysis_fn=None,
        chat_fn=None,
    ) -> None:
        self.supervisor = supervisor
        self.store = store
        self.telegram = telegram
        self.allowed_user_ids = {str(value) for value in allowed_user_ids}
        self.action_executor = action_executor
        self.analysis_fn = analysis_fn
        self.chat_fn = chat_fn

    def handle(self, message: TelegramMessage) -> str:
        if message.user_id not in self.allowed_user_ids:
            return "unauthorized"
        command = parse_command(message.text)
        if command is None:
            response = self._chat(message.text)
            self.telegram.send(response, chat_id=message.chat_id)
            return response
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

    def _chat(self, question: str) -> str:
        lowered = question.casefold()
        try:
            report = self.supervisor.observe()
        except LookupError:
            return "В базе пока нет ingestion run для анализа."
        if any(word in lowered for word in ("повтори", "запусти", "перезапусти", "retry")):
            return (
                "Я не запускаю ingestion из Telegram. Production-runner запускается по расписанию "
                "Coolify каждые 6 часов и повторит failed запуск. Я сообщу результат и причину."
            )
        if self.chat_fn is not None:
            answer = self.chat_fn(report, question)
            if answer:
                return answer
        return explain_report(report)

    def _propose(self, run_id: str) -> str:
        retry_match = RETRY_ACTION_RE.fullmatch(run_id)
        if retry_match:
            if self.action_executor is None:
                return "actions_not_enabled"
            entity_type, entity_id, stage = retry_match.groups()
            if stage not in {"extract_artist_tags", "extract_event_tags"}:
                return "unsupported_retry_stage"
            state = self.store.load()
            actions = state.setdefault("actions", {})
            action_id = f"action-{len(actions) + 1}"
            created_at = datetime.now(timezone.utc)
            actions[action_id] = {
                "id": action_id,
                "type": "retry_quarantine",
                "arguments": {
                    "entity_type": entity_type,
                    "entity_id": int(entity_id),
                    "stage": stage,
                },
                "status": "pending",
                "created_at": created_at.isoformat(),
                "expires_at": (created_at + timedelta(hours=1)).isoformat(),
            }
            self.store.save(state)
            return f"Proposed {action_id}; explicit approval is required."
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
        analysis = analyze_report(report)
        llm_analysis = self.analysis_fn(report) if self.analysis_fn else None
        if llm_analysis:
            analysis["llm"] = llm_analysis
        return json.dumps(
            {
                "summary": explain_report(report),
                "run_id": report["run_id"],
                "stages": report["stages"],
                "analysis": analysis,
            },
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
        if action.get("status") in {"approved", "completed", "failed", "rejected"}:
            if action.get("status") in {"approved", "completed"} and action.get("result"):
                return json.dumps(action["result"], sort_keys=True)
            return str(action["status"])
        try:
            expired = datetime.now(timezone.utc) >= datetime.fromisoformat(str(action["expires_at"]))
        except (KeyError, TypeError, ValueError):
            expired = True
        if expired:
            action["status"] = "expired"
            self.store.save(state)
            return "expired"
        if command == "reject":
            action["status"] = "rejected"
            self.store.save(state)
            return "rejected"
        if action.get("type") == "retry_quarantine" and self.action_executor is None:
            return "actions_not_enabled"
        action["status"] = "approved"
        if self.action_executor is not None:
            try:
                action["result"] = self.action_executor.execute(action)
                action["status"] = "completed"
            except Exception as exc:
                action["status"] = "failed"
                action["result"] = {"status": "failed", "error_type": type(exc).__name__}
        self.store.save(state)
        return str(action["status"])
