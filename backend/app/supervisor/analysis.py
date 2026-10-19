from __future__ import annotations

from typing import Any


def analyze_report(report: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic next-step guidance; no model or external call."""
    category = report.get("failure_category")
    if category == "quota_exhausted":
        recommendation = "wait_for_provider_quota_then_resume"
        explanation = "The provider quota is exhausted; do not retry until the quota window resets."
    elif category == "authentication":
        recommendation = "check_provider_configuration"
        explanation = "Authentication/configuration must be fixed before any retry."
    elif category == "unknown_system":
        recommendation = "inspect_failed_stage"
        explanation = "An unknown/system failure requires operator review; no automatic retry is proposed."
    else:
        recommendation = "no_action"
        explanation = "No recoverable failure is currently recorded for this run."
    return {
        "category": category,
        "recommendation": recommendation,
        "explanation": explanation,
        "run_id": report.get("run_id"),
    }


def explain_report(report: dict[str, Any]) -> str:
    """Build a short operator-facing explanation from persisted safe fields."""
    run_id = report.get("run_id", "?")
    status = report.get("status", "unknown")
    progress = report.get("progress", {})
    events = progress.get("events", {})
    artists = progress.get("artists", {})
    lines = [
        f"Run {run_id}: status={status}.",
        f"Events: {events.get('completed', 0)}/{events.get('total', 0)}; "
        f"artists: {artists.get('completed', 0)}/{artists.get('total', 0)}.",
    ]
    stages = report.get("stages", [])
    completed = [str(stage.get("name")) for stage in stages if stage.get("status") == "succeeded"]
    failed = [stage for stage in stages if stage.get("status") == "failed"]
    if completed:
        lines.append("Completed stages: " + ", ".join(completed) + ".")
    if failed:
        for stage in failed:
            name = sanitize_for_explanation(stage.get("name"), 120)
            error = sanitize_for_explanation(stage.get("error") or "no error recorded", 700)
            lines.append(f"Failed stage: {name}; error: {error}.")
    analysis = analyze_report(report)
    lines.append(f"Recommendation: {analysis['explanation']}")
    return "\n".join(lines)


def sanitize_for_explanation(value: object, limit: int) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."
