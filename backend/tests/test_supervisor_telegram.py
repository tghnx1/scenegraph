from __future__ import annotations

from pathlib import Path

from app.supervisor.state import DeterministicSupervisor, ImportRunSnapshot, JsonStateStore
from app.supervisor.analysis import OptionalLLMAnalyzer
from app.supervisor.telegram import (
    TelegramCommandService,
    TelegramMessage,
    parse_command,
)


class SnapshotReader:
    def __init__(self) -> None:
        self.snapshot = ImportRunSnapshot(
            run_id="42",
            pipeline_name="full-pipeline",
            status="failed",
            min_date="2026-10-18",
            max_date="2026-10-18",
            event_count=10,
            artist_count=4,
            events_imported=8,
            artists_imported=3,
            event_tags=8,
            artist_tags=3,
            event_embeddings=0,
            artist_embeddings=0,
            error="provider quota usage limit",
            started_at=None,
            finished_at=None,
            updated_at=None,
            stages=(),
            quarantine=(),
        )

    def read(self, run_id: int | None = None) -> ImportRunSnapshot:
        if run_id is not None and str(run_id) != self.snapshot.run_id:
            raise LookupError("import run not found")
        return self.snapshot


class FakeTelegram:
    def __init__(self, updates: list[TelegramMessage] | None = None) -> None:
        self.updates = updates or []
        self.sent: list[tuple[str, str]] = []
        self.offsets: list[int | None] = []

    def send(self, message: str, *, chat_id: str) -> None:
        self.sent.append((message, chat_id))

    def get_updates(self, *, offset: int | None = None, timeout: int = 0) -> list[TelegramMessage]:
        self.offsets.append(offset)
        return list(self.updates)


def make_service(tmp_path: Path, telegram: FakeTelegram, action_executor=None) -> TelegramCommandService:
    supervisor = DeterministicSupervisor(
        SnapshotReader(),
        JsonStateStore(tmp_path / "state.json"),
        telegram=_NotificationSink(),
    )
    return TelegramCommandService(
        supervisor,
        supervisor.store,
        telegram,
        allowed_user_ids={"trusted-user"},
        action_executor=action_executor,
    )


class _NotificationSink:
    def send(self, _message: str) -> None:
        return None


def test_command_parser_is_strict_and_allowlisted() -> None:
    assert parse_command("status").name == "status"
    assert parse_command("/details 42").argument == "42"
    assert parse_command("details 42 extra") is None
    assert parse_command("run_shell anything") is None
    assert parse_command("hello") is None


def test_unauthorized_user_cannot_execute_command(tmp_path: Path) -> None:
    telegram = FakeTelegram()
    service = make_service(tmp_path, telegram)

    assert service.handle(TelegramMessage(1, "untrusted-user", "chat", "status")) == "unauthorized"
    assert telegram.sent == []


def test_commands_require_valid_run_id_and_actions_are_idempotent(tmp_path: Path) -> None:
    telegram = FakeTelegram()
    service = make_service(tmp_path, telegram)

    assert service.handle(TelegramMessage(1, "trusted-user", "chat", "details nope")) == "invalid_run_id"
    assert service.handle(TelegramMessage(2, "trusted-user", "chat", "propose 42")).startswith("Proposed action-1")
    assert service.handle(TelegramMessage(3, "trusted-user", "chat", "approve action-1")) == "approved"
    assert service.handle(TelegramMessage(4, "trusted-user", "chat", "approve action-1")) == "approved"
    assert service.handle(TelegramMessage(5, "trusted-user", "chat", "reject action-1")) == "approved"

    state = service.store.load()
    assert state["actions"]["action-1"]["status"] == "approved"
    assert all("provider quota" not in message for message, _ in telegram.sent)


def test_details_includes_human_readable_summary_and_json(tmp_path: Path) -> None:
    telegram = FakeTelegram()
    service = make_service(tmp_path, telegram)

    response = service.handle(TelegramMessage(1, "trusted-user", "chat", "details 42"))

    assert '"summary":' in response
    assert "Run 42: status=failed." in response
    assert '"analysis":' in response


def test_poll_once_persists_next_update_id(tmp_path: Path) -> None:
    telegram = FakeTelegram([TelegramMessage(17, "trusted-user", "chat", "status")])
    service = make_service(tmp_path, telegram)

    assert service.poll_once() == 1
    assert service.store.load()["telegram"]["next_update_id"] == 18
    assert service.poll_once() == 1
    assert telegram.offsets == [None, 18]


def test_approved_quarantine_retry_uses_bounded_action_executor(tmp_path: Path) -> None:
    telegram = FakeTelegram()

    class FakeExecutor:
        def __init__(self) -> None:
            self.actions: list[dict] = []

        def execute(self, action: dict) -> dict:
            self.actions.append(action)
            return {"status": "resolved", "entity_type": "artist", "entity_id": 1481}

    executor = FakeExecutor()
    service = make_service(tmp_path, telegram, executor)

    proposal = service.handle(
        TelegramMessage(1, "trusted-user", "chat", "propose retry_quarantine:artist:1481:extract_artist_tags")
    )
    assert proposal.startswith("Proposed action-1")
    assert service.handle(TelegramMessage(2, "trusted-user", "chat", "approve action-1")) == "completed"
    assert service.handle(TelegramMessage(3, "trusted-user", "chat", "approve action-1")) == '{"entity_id": 1481, "entity_type": "artist", "status": "resolved"}'
    assert len(executor.actions) == 1


def test_optional_llm_analyzer_only_receives_compact_operational_report() -> None:
    class FakeCompletions:
        def __init__(self) -> None:
            self.request = None

        def create(self, **kwargs):
            self.request = kwargs
            return type("Response", (), {"choices": [type("Choice", (), {"message": type("Message", (), {"content": '{"summary":"quota hit","cause":"provider limit","next_step":"wait"}'})()})()]})()

    completions = FakeCompletions()
    client = type("Client", (), {"chat": type("Chat", (), {"completions": completions})()})()
    analyzer = OptionalLLMAnalyzer(client, "test-model")

    result = analyzer(
        {
            "run_id": "42",
            "status": "failed",
            "failure_category": "quota_exhausted",
            "progress": {"events": {"remaining": 2}},
            "stages": [{"name": "extract", "status": "failed", "error": "quota"}],
            "biography": "must not be sent",
        }
    )

    assert result["cause"] == "provider limit"
    assert "biography" not in completions.request["messages"][1]["content"]
