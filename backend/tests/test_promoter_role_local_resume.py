import pytest

from app import promoter_role_local_resume as resume


class Cursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


def test_quota_wait_uses_persisted_deadline(monkeypatch):
    class Connection:
        def execute(self, _query, _parameters):
            return Cursor((42,))

        def commit(self):
            pass

    slept = []
    monkeypatch.setattr(resume.time, "sleep", slept.append)
    assert resume.wait_for_quota(Connection(), 42)
    assert slept == [42.0]


def test_non_quota_pause_does_not_wait(monkeypatch):
    class Connection:
        def execute(self, _query, _parameters):
            return Cursor(None)

        def commit(self):
            pass

    monkeypatch.setattr(resume.time, "sleep", lambda _seconds: pytest.fail("must not sleep"))
    assert not resume.wait_for_quota(Connection(), 42)


def test_resume_rejects_nonlocal_database(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@example.invalid/db")
    monkeypatch.setattr("sys.argv", ["resume", "--run-id", "42"])
    monkeypatch.setattr(resume.psycopg, "connect", lambda *_args: pytest.fail("must not connect"))
    with pytest.raises(SystemExit, match="local Compose database"):
        resume.main()
