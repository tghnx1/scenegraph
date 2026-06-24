from contextlib import contextmanager

from app import db


@contextmanager
def use_db_connection():
    """Open and close one short-lived database checkout through the app helper."""
    generator = db.get_db()
    connection = next(generator)
    try:
        yield connection
    finally:
        try:
            next(generator)
        except StopIteration:
            pass


def test_db_connection_smoke():
    """Exercise two sequential checkouts so both current and legacy stacks can benchmark it."""
    with use_db_connection() as first_connection:
        assert first_connection is not None

    with use_db_connection() as second_connection:
        assert second_connection is not None
