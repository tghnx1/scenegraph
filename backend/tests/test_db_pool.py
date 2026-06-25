from contextlib import contextmanager

from app import db


class FakeConnection:
    def __init__(self, label: str):
        self.label = label
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def close(self):
        self.closed = True


@contextmanager
def use_db_connection():
    generator = db.get_db()
    connection = next(generator)
    try:
        yield connection
    finally:
        try:
            next(generator)
        except StopIteration:
            pass


def test_get_db_opens_direct_connections(monkeypatch):
    created_connections: list[FakeConnection] = []

    def fake_connect(*args, **kwargs):
        connection = FakeConnection(f"connection-{len(created_connections) + 1}")
        created_connections.append(connection)
        return connection

    monkeypatch.setattr(db.psycopg, "connect", fake_connect)

    with use_db_connection() as first_connection:
        assert first_connection.label == "connection-1"
    assert first_connection.closed is True

    with use_db_connection() as second_connection:
        assert second_connection.label == "connection-2"
    assert second_connection.closed is True

    assert len(created_connections) == 2
