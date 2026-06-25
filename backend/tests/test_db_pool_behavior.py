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


class FakePool:
    instances: list["FakePool"] = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.checkout_count = 0
        self.closed = False
        self.connection_object = FakeConnection(f"connection-{len(self.instances) + 1}")
        self.instances.append(self)

    @contextmanager
    def connection(self):
        self.checkout_count += 1
        yield self.connection_object

    def close(self):
        self.closed = True


@contextmanager
def use_db_connection():
    """Open and close one short-lived database checkout through the app helper."""
    with db.get_connection() as connection:
        yield connection


def test_get_connection_uses_one_shared_pool(monkeypatch):
    """Ensure the backend uses one shared pool and reuses pooled connections."""
    db.close_connection_pool()
    FakePool.instances.clear()
    monkeypatch.setattr(db, "ConnectionPool", FakePool)

    try:
        pool_a = db.get_connection_pool()
        pool_b = db.get_connection_pool()

        assert pool_a is pool_b
        assert len(FakePool.instances) == 1

        with use_db_connection() as first_connection:
            assert first_connection.label == "connection-1"

        with use_db_connection() as second_connection:
            assert second_connection is first_connection

        assert pool_a.checkout_count == 2
    finally:
        db.close_connection_pool()
