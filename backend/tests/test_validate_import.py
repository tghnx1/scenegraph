from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "postgresql://test")

from scripts.validate_import import minimum_artists_for_scope


def test_empty_artist_scope_does_not_require_an_artist_row() -> None:
    assert minimum_artists_for_scope([], 1) == 0


def test_non_empty_or_unbounded_artist_scope_keeps_configured_minimum() -> None:
    assert minimum_artists_for_scope([123], 1) == 1
    assert minimum_artists_for_scope(None, 1) == 1
