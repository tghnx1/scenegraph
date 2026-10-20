from __future__ import annotations

from typing import Any
import json
import logging
import os

from .state import sanitize


LOGGER = logging.getLogger(__name__)


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
        lines.append(
            "Persisted scope snapshot at failure: "
            f"event tag records={report.get('event_tags', 0)}; "
            f"artist tag records={report.get('artist_tags', 0)}."
        )
    elif report.get("error"):
        lines.append(
            "Run error: " + sanitize_for_explanation(report.get("error"), 700) + "."
        )
    analysis = analyze_report(report)
    lines.append(f"Recommendation: {analysis['explanation']}")
    return "\n".join(lines)


def sanitize_for_explanation(value: object, limit: int) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def compact_report(report: dict[str, Any]) -> dict[str, Any]:
    """Keep optional model input limited to operational metadata."""
    return {
        "run_id": report.get("run_id"),
        "status": report.get("status"),
        "failure_category": report.get("failure_category"),
        "progress": report.get("progress", {}),
        "metrics": {
            "events_imported": report.get("events_imported", 0),
            "artists_imported": report.get("artists_imported", 0),
            "event_tags": report.get("event_tags", 0),
            "artist_tags": report.get("artist_tags", 0),
            "event_embeddings": report.get("event_embeddings", 0),
            "artist_embeddings": report.get("artist_embeddings", 0),
        },
        "stages": [
            {
                "name": sanitize_for_explanation(stage.get("name"), 120),
                "status": sanitize_for_explanation(stage.get("status"), 40),
                "error": sanitize_for_explanation(stage.get("error") or "", 500),
            }
            for stage in report.get("stages", [])
        ],
    }


class OptionalLLMAnalyzer:
    """Best-effort report analysis with deterministic fallback outside this class."""

    def __init__(self, client: Any, model: str, *, temperature: int | float = 0) -> None:
        self.client = client
        self.model = model
        self.temperature = temperature

    @staticmethod
    def _log_provider_failure(exc: Exception) -> None:
        status = getattr(exc, "status_code", None)
        LOGGER.warning(
            "Supervisor LLM analysis unavailable: error_type=%s status_code=%s; using deterministic fallback",
            type(exc).__name__,
            status if isinstance(status, int) else "unknown",
        )

    def __call__(self, report: dict[str, Any]) -> dict[str, str] | None:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Explain an ingestion run using only the supplied operational metadata. "
                            "Return JSON with keys summary, cause, next_step. Do not invent facts."
                        ),
                    },
                    {"role": "user", "content": json.dumps(compact_report(report), sort_keys=True)},
                ],
                temperature=self.temperature,
                max_tokens=300,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            parsed = json.loads(content or "{}")
            if not isinstance(parsed, dict):
                return None
            result = {}
            for key in ("summary", "cause", "next_step"):
                value = parsed.get(key)
                if value:
                    result[key] = sanitize_for_explanation(value, 600)
            return result or None
        except Exception as exc:
            self._log_provider_failure(exc)
            return None

    def answer(self, report: dict[str, Any], question: str) -> str | None:
        """Answer an operator question using only the compact run projection."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a cautious ingestion operations analyst. Answer the operator's "
                            "question using only the supplied run metadata. Do not invent causes, "
                            "do not expose secrets, and do not claim that you ran or changed anything. "
                            "If the data is insufficient, say so. Keep the answer under 1200 characters."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"question": sanitize_for_explanation(question, 512), "run": compact_report(report)},
                            sort_keys=True,
                        ),
                    },
                ],
                temperature=self.temperature,
                max_tokens=350,
            )
            content = response.choices[0].message.content
            return sanitize_for_explanation(content, 1200) if content else None
        except Exception as exc:
            self._log_provider_failure(exc)
            return None


def build_optional_llm_analyzer() -> OptionalLLMAnalyzer | None:
    if os.environ.get("SUPERVISOR_LLM_ANALYSIS_ENABLED", "false").strip().lower() not in {"1", "true", "yes"}:
        return None
    provider = os.environ.get("SUPERVISOR_ANALYSIS_PROVIDER", "").strip().lower()
    model = os.environ.get("SUPERVISOR_ANALYSIS_MODEL", "").strip()
    if not provider or not model:
        return None
    try:
        if provider == "azure":
            from openai import AzureOpenAI

            return OptionalLLMAnalyzer(
                AzureOpenAI(
                    api_key=os.environ["AZURE_OPENAI_API_KEY"],
                    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                    api_version=os.environ["AZURE_OPENAI_CHAT_API_VERSION"],
                ),
                model,
            )
        if provider in {"openai", "moonshot", "kimi_code"}:
            from openai import OpenAI

            key_name = {
                "openai": "OPENAI_API_KEY",
                "moonshot": "MOONSHOT_API_KEY",
                "kimi_code": "KIMI_API_KEY",
            }[provider]
            key = os.environ.get(key_name, "").strip()
            if not key:
                return None
            base_url = os.environ.get(
                {
                    "openai": "OPENAI_BASE_URL",
                    "moonshot": "MOONSHOT_BASE_URL",
                    "kimi_code": "KIMI_BASE_URL",
                }[provider],
                "",
            ).strip()
            temperature = 1 if provider == "kimi_code" else 0
            return OptionalLLMAnalyzer(
                OpenAI(api_key=key, base_url=base_url or None),
                model,
                temperature=temperature,
            )
    except Exception:
        return None
    return None
