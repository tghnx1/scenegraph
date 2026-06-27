from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql://scenegraph:change-me@db:5432/scenegraph")

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.routers import artists as artists_router
from scripts.import_events import import_artist_biographies


class FakeCursor:
    def __init__(self, responses: list[dict[str, object] | None], rowcounts: list[int] | None = None):
        self._responses = list(responses)
        self._rowcounts = list(rowcounts or [])
        self.executed: list[tuple[str, tuple | None]] = []
        self.rowcount = 0
        self._current_response: dict[str, object] | None = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query: str, params=None):
        self.executed.append((" ".join(query.split()), params))
        self._current_response = self._responses.pop(0) if self._responses else None
        self.rowcount = self._rowcounts.pop(0) if self._rowcounts else 0

    def fetchone(self):
        return self._current_response


class FakeConnection:
    def __init__(self, cursor: FakeCursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self._cursor


def test_import_artist_biographies_preserves_manually_edited_bio():
    cursor = FakeCursor(
        responses=[{"biography_status": "manually_edited"}],
        rowcounts=[0, 1],
    )

    updated, unchanged, missing_artist = import_artist_biographies(
        cursor,
        [
            {
                "id": "2178",
                "biography": "Source biography that should not overwrite manual text.",
                "biography_url": "https://example.com/source",
                "status": "published",
            }
        ],
    )

    assert (updated, unchanged, missing_artist) == (1, 0, 0)
    assert len(cursor.executed) == 2
    select_sql, select_params = cursor.executed[0]
    update_sql, update_params = cursor.executed[1]
    assert "SELECT biography_status FROM artists" in select_sql
    assert select_params == ("2178",)
    assert "SET biography_url = COALESCE(%s, biography_url)" in update_sql
    assert "biography = %s" not in update_sql
    assert update_params == ("https://example.com/source", "2178", "https://example.com/source")


def test_import_artist_biographies_still_updates_bio_when_not_manual():
    cursor = FakeCursor(
        responses=[{"biography_status": "imported"}],
        rowcounts=[0, 1],
    )

    updated, unchanged, missing_artist = import_artist_biographies(
        cursor,
        [
            {
                "id": "2178",
                "biography": "Fresh source biography.",
                "biography_url": "https://example.com/source",
                "status": "published",
            }
        ],
    )

    assert (updated, unchanged, missing_artist) == (1, 0, 0)
    update_sql, update_params = cursor.executed[1]
    assert "SET biography = %s" in update_sql
    assert "biography_status = %s" in update_sql
    assert update_params[0] == "Fresh source biography."


def test_patch_biography_stores_normalized_copy(monkeypatch):
    cursor = FakeCursor(
        responses=[
            {"role": "admin", "artist_id": None},
            {"id": 2178, "name": "Artist", "biography": "Dark\n Disco", "biography_normalized": "Dark Disco"},
        ],
        rowcounts=[0, 1],
    )
    connection = FakeConnection(cursor)

    monkeypatch.setattr(artists_router, "get_connection", lambda: connection)

    response = asyncio.run(
        artists_router.update_artist_biography(
            2178,
            artists_router.ArtistBiographyUpdate(biography="  Dark\n Disco "),
            current_user_id=1,
        )
    )

    assert response.id == 2178
    assert response.name == "Artist"
    assert response.biography == "Dark\n Disco"
    update_sql, update_params = cursor.executed[1]
    assert "biography_normalized = %s" in update_sql
    assert update_params == ("Dark\n Disco", "Dark Disco", 2178)
