from unittest.mock import MagicMock

import psycopg

from app import promoter_role_queue
from scripts import import_events


def test_queue_failure_does_not_undo_committed_import(monkeypatch, capsys):
    connection = MagicMock()
    manager = MagicMock()
    manager.__enter__.return_value = connection
    monkeypatch.setattr(import_events.psycopg, "connect", lambda *a, **kw: manager)
    monkeypatch.setattr(import_events, "load_events", lambda path: [{"id": "ra1"}])
    monkeypatch.setattr(import_events, "import_event", lambda cursor, event: None)
    monkeypatch.setattr(promoter_role_queue, "enqueue_imported_ra_events", lambda *args: (_ for _ in ()).throw(psycopg.OperationalError("hidden")))
    monkeypatch.setattr("sys.argv", ["import_events.py", "unused.json"])
    monkeypatch.setenv("PROMOTER_ROLE_QUEUE_ENABLED", "true")
    monkeypatch.delenv("ARTIST_BIOGRAPHIES_JSON_PATH", raising=False)
    import_events.main()
    connection.commit.assert_called_once()
    output = capsys.readouterr().out
    assert "imported events remain committed" in output
    assert "hidden" not in output
