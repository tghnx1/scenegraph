from __future__ import annotations

from datetime import date
from typing import Any

from app.coverage import CoverageConfig, CoverageOperations


class ApprovedActionExecutor:
    """Execute only action types backed by existing bounded application paths."""

    def __init__(self, database_url: str, *, config: CoverageConfig | None = None) -> None:
        self.database_url = database_url
        self.config = config or CoverageConfig.from_env()

    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        if action.get("type") != "retry_quarantine":
            return {"status": "approved", "action_type": str(action.get("type"))}
        args = action.get("arguments")
        if not isinstance(args, dict):
            raise ValueError("retry_quarantine action arguments are invalid")
        entity_type = str(args.get("entity_type", ""))
        stage = str(args.get("stage", ""))
        entity_id = int(args.get("entity_id", 0))
        operations = CoverageOperations(
            min_date=date(2000, 1, 1).isoformat(),
            max_date=date(2000, 1, 1).isoformat(),
            apply=True,
            allow_quarantine_retry=True,
            config=self.config,
            database_url=self.database_url,
        )
        return operations.retry_quarantine(entity_type, entity_id, stage)
