"""Deterministic, approval-gated ingestion supervisor components."""

from .state import DeterministicSupervisor, ProductRunReader

__all__ = ["DeterministicSupervisor", "ProductRunReader"]
