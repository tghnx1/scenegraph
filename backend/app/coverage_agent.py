from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from app.coverage import CoverageOperations


COVERAGE_AGENT_INSTRUCTIONS = """
You are CoverageAgent, responsible for Scenegraph ingestion coverage.

You may only make decisions based on structured results from the provided tools.

Rules:
1. Never infer missing events from titles, descriptions, counts alone, or intuition.
2. audit_date and audit_range are the authority for coverage.
3. If missing_count is zero, do not propose or run backfill.
4. In apply mode, if missing_count is greater than zero, run backfill only for that audited date.
5. After every backfill, verify the same date.
6. Never run the same backfill date more than once in one invocation.
7. Quarantined enrichment does not mean the event is absent from the database.
8. Unknown or systemic errors must stop recovery and be reported.
9. Do not invent IDs, dates, or tool results.
10. Do not claim a repair until verify_date confirms missing_count is zero.

Return a concise summary grounded only in tool results.
""".strip()


def build_coverage_tools(
    operations: CoverageOperations,
    *,
    structured_tool_class=None,
) -> list[Any]:
    if structured_tool_class is None:
        from langchain_core.tools import StructuredTool

        structured_tool_class = StructuredTool

    tools = [
        structured_tool_class.from_function(
            name="audit_date",
            description="Deterministically compare RA and Scenegraph event IDs for one requested date.",
            func=operations.audit_date,
        ),
        structured_tool_class.from_function(
            name="audit_range",
            description="Deterministically audit each date in a bounded requested date range.",
            func=operations.audit_range,
        ),
        structured_tool_class.from_function(
            name="quarantine_status",
            description="List compact unresolved enrichment quarantine status; quarantine is not missing coverage.",
            func=operations.quarantine_status,
        ),
    ]
    if operations.apply:
        tools.extend(
            [
                structured_tool_class.from_function(
                    name="run_backfill",
                    description="Run the fixed Scenegraph full pipeline for one audited date with missing events.",
                    func=operations.run_backfill,
                ),
                structured_tool_class.from_function(
                    name="verify_date",
                    description="Repeat deterministic coverage comparison after a backfill for the same date.",
                    func=operations.verify_date,
                ),
            ]
        )
    if operations.apply and operations.allow_quarantine_retry:
        tools.append(
            structured_tool_class.from_function(
                name="retry_quarantine",
                description="Retry one supported unresolved event-tag or artist-tag quarantine item once.",
                func=operations.retry_quarantine,
            )
        )
    return tools


def build_coverage_llm():
    from langchain_openai import AzureChatOpenAI

    model = os.environ.get("COVERAGE_AGENT_MODEL", "").strip()
    if not model:
        raise RuntimeError("COVERAGE_AGENT_MODEL must be set")
    required = {
        "AZURE_OPENAI_API_KEY": os.environ.get("AZURE_OPENAI_API_KEY", "").strip(),
        "AZURE_OPENAI_ENDPOINT": os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip(),
        "AZURE_OPENAI_CHAT_API_VERSION": os.environ.get("AZURE_OPENAI_CHAT_API_VERSION", "").strip(),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing CoverageAgent Azure configuration: {', '.join(missing)}")
    return AzureChatOpenAI(
        azure_deployment=model,
        api_key=required["AZURE_OPENAI_API_KEY"],
        azure_endpoint=required["AZURE_OPENAI_ENDPOINT"],
        api_version=required["AZURE_OPENAI_CHAT_API_VERSION"],
        temperature=0,
    )


class CoverageAgent:
    def __init__(
        self,
        operations: CoverageOperations,
        *,
        llm=None,
        agent_class=None,
        structured_tool_class=None,
    ) -> None:
        if agent_class is None:
            from motleycrew.agents.langchain import ReActToolCallingMotleyAgent

            agent_class = ReActToolCallingMotleyAgent
        tools = build_coverage_tools(
            operations,
            structured_tool_class=structured_tool_class,
        )
        self.operations = operations
        self.tools = tools
        self.agent = agent_class(
            name="CoverageAgent",
            description=COVERAGE_AGENT_INSTRUCTIONS,
            prompt=COVERAGE_AGENT_INSTRUCTIONS + "\n\n{prompt}",
            tools=tools,
            llm=llm or build_coverage_llm(),
            chat_history=False,
            max_iterations=20,
            handle_parsing_errors=False,
            verbose=False,
        )

    def run(self) -> dict[str, Any]:
        mode = "APPLY" if self.operations.apply else "PLAN/READ-ONLY"
        retry = "enabled" if self.operations.allow_quarantine_retry else "disabled"
        if self.operations.apply:
            task = (
                "Audit the range, repair only deterministic missing-event gaps, verify every "
                "backfill, inspect quarantine status, and summarize."
            )
        else:
            task = (
                "Audit the range and inspect quarantine status. This is structurally read-only: "
                "report dates with missing events as proposed repair dates, and do not attempt "
                "backfill, verification, or quarantine retry."
            )
        prompt = (
            f"Audit Scenegraph coverage from {self.operations.min_date.isoformat()} through "
            f"{self.operations.max_date.isoformat()}. Mode: {mode}. "
            f"Quarantine retry: {retry}. {task}"
        )
        output = self.agent.invoke({"prompt": prompt})
        report = self.operations.report()
        agent_output = output.get("output", output) if isinstance(output, dict) else output
        if isinstance(agent_output, str) and len(agent_output) > 4000:
            agent_output = agent_output[:4000] + "...[truncated]"
        report["agent_output"] = agent_output
        return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit and safely repair Scenegraph historical coverage.")
    parser.add_argument("mode", nargs="?", choices=("agent", "audit"), default="agent")
    parser.add_argument("--min-date", required=True)
    parser.add_argument("--max-date", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--retry-quarantine", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.retry_quarantine and not args.apply:
        raise SystemExit("--retry-quarantine requires --apply")
    if args.mode == "audit" and args.apply:
        raise SystemExit("Deterministic audit mode is read-only and does not accept --apply")

    operations = CoverageOperations(
        min_date=args.min_date,
        max_date=args.max_date,
        apply=args.apply,
        allow_quarantine_retry=args.retry_quarantine,
    )
    if args.mode == "audit":
        result = {
            "coverage": operations.audit_range(args.min_date, args.max_date),
            "quarantine": operations.quarantine_status(),
            "report": operations.report(),
        }
    else:
        result = CoverageAgent(operations).run()
    print(json.dumps(result, default=str, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"CoverageAgent failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
