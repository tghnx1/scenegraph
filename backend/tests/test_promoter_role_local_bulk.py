import pytest

from app import promoter_role_local_bulk as bulk


def test_bulk_rejects_nonlocal_database_before_connecting(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@example.invalid/db")
    monkeypatch.setattr("sys.argv", ["promoter_role_local_bulk", "--apply"])
    monkeypatch.setattr(bulk.psycopg, "connect", lambda *args: pytest.fail("must not connect"))
    with pytest.raises(SystemExit, match="local Compose database"):
        bulk.main()


def test_bulk_without_apply_does_not_create_runs(monkeypatch, capsys):
    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, _query):
            return [(1,), (2,)]

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@db/test")
    monkeypatch.setattr("sys.argv", ["promoter_role_local_bulk"])
    monkeypatch.setattr(bulk.psycopg, "connect", lambda _url: Connection())
    monkeypatch.setattr(bulk, "create_run", lambda *args: pytest.fail("dry run must not write"))
    assert bulk.main() == 0
    assert '"snapshot_events": 2' in capsys.readouterr().out
