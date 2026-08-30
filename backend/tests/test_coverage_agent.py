from __future__ import annotations

import json
import sys

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from app.coverage import CoverageOperations
from app import coverage_agent
from app.coverage_agent import CoverageAgent, build_coverage_tools


DATE = "2026-08-15"


class FakeStructuredTool:
    def __init__(self, *, name, description, func):
        self.name = name
        self.description = description
        self.func = func

    @classmethod
    def from_function(cls, **kwargs):
        return cls(**kwargs)

    def invoke(self, arguments):
        return self.func(**arguments)


def make_operations(*, missing: bool, apply: bool = True) -> CoverageOperations:
    db_results = iter((set(), {"1"})) if missing else iter(({"1"},))
    return CoverageOperations(
        min_date=DATE,
        max_date=DATE,
        apply=apply,
        database_url="postgresql://test/scenegraph",
        ra_fetcher=lambda _start, _end: {"1"},
        db_fetcher=lambda _url, _date: next(db_results),
        run_command=lambda *_args, **_kwargs: None,
        quarantine_fetcher=lambda *_args, **_kwargs: [],
    )


class DeterministicFakeMotleyAgent:
    received_tool_names: list[str] = []

    def __init__(self, *, tools, **_kwargs):
        self.tools = {tool.name: tool for tool in tools}
        type(self).received_tool_names = list(self.tools)

    def invoke(self, _prompt):
        audit = self.tools["audit_range"].invoke({"min_date": DATE, "max_date": DATE})
        for item in audit["dates"]:
            if item["missing_count"]:
                self.tools["run_backfill"].invoke({"date": item["date"]})
                self.tools["verify_date"].invoke({"date": item["date"]})
        self.tools["quarantine_status"].invoke({})
        return {"output": "structured fake run complete"}


class ToolBindableFakeChatModel(FakeMessagesListChatModel):
    def bind_tools(self, tools=None, **_kwargs):
        return self


def test_motley_agent_receives_only_intended_tools_and_skips_complete_backfill():
    operations = make_operations(missing=False)

    report = CoverageAgent(
        operations,
        llm=object(),
        agent_class=DeterministicFakeMotleyAgent,
        structured_tool_class=FakeStructuredTool,
    ).run()

    assert DeterministicFakeMotleyAgent.received_tool_names == [
        "audit_date",
        "audit_range",
        "run_backfill",
        "verify_date",
        "quarantine_status",
    ]
    assert report["backfilled_dates"] == []


def test_agent_backfills_missing_date_then_verifies_and_reports_repair():
    operations = make_operations(missing=True)

    report = CoverageAgent(
        operations,
        llm=object(),
        agent_class=DeterministicFakeMotleyAgent,
        structured_tool_class=FakeStructuredTool,
    ).run()

    assert report["backfilled_dates"] == [DATE]
    assert [action["action"] for action in report["actions"]][-3:] == [
        "run_backfill",
        "verify_date",
        "quarantine_status",
    ]
    assert report["actions"][-2]["status"] == "repaired"


def test_retry_tool_is_exposed_only_when_explicitly_enabled():
    disabled = make_operations(missing=False)
    enabled = make_operations(missing=False)
    enabled.allow_quarantine_retry = True

    disabled_names = [
        tool.name
        for tool in build_coverage_tools(
            disabled,
            include_quarantine_retry=False,
            structured_tool_class=FakeStructuredTool,
        )
    ]
    enabled_names = [
        tool.name
        for tool in build_coverage_tools(
            enabled,
            include_quarantine_retry=True,
            structured_tool_class=FakeStructuredTool,
        )
    ]

    assert "retry_quarantine" not in disabled_names
    assert enabled_names[-1] == "retry_quarantine"


def test_real_motleycrew_agent_api_runs_without_network():
    operations = make_operations(missing=False, apply=False)
    llm = ToolBindableFakeChatModel(responses=[AIMessage(content="No actions requested")])

    report = CoverageAgent(operations, llm=llm).run()

    assert report["agent_output"] == "No actions requested"
    assert report["backfilled_dates"] == []


def test_deterministic_audit_cli_does_not_construct_agent(monkeypatch, capsys):
    class FakeOperations:
        def __init__(self, **_kwargs):
            pass

        def audit_range(self, min_date, max_date):
            return {"min_date": min_date, "max_date": max_date, "status": "complete"}

        def quarantine_status(self):
            return {"total": 0, "events": 0, "artists": 0, "items": []}

        def report(self):
            return {"apply": False, "actions": []}

    monkeypatch.setattr(coverage_agent, "CoverageOperations", FakeOperations)
    monkeypatch.setattr(
        coverage_agent,
        "CoverageAgent",
        lambda *_args, **_kwargs: pytest.fail("audit mode must not construct the LLM agent"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["coverage_agent.py", "audit", "--min-date", DATE, "--max-date", DATE],
    )

    assert coverage_agent.main() == 0
    assert json.loads(capsys.readouterr().out)["coverage"]["status"] == "complete"


def test_retry_quarantine_cli_flag_requires_apply(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "coverage_agent.py",
            "--min-date",
            DATE,
            "--max-date",
            DATE,
            "--retry-quarantine",
        ],
    )

    with pytest.raises(SystemExit, match="requires --apply"):
        coverage_agent.main()
