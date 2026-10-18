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
