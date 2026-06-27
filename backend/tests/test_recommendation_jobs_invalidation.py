from app.recommendations.jobs import invalidate_artist_promoter_jobs


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.executed.append((" ".join(query.split()), params))

    def fetchall(self):
        return list(self.rows)


class FakeConnection:
    def __init__(self, rows):
        self.cursor_obj = FakeCursor(rows)
        self.transaction_entries = 0

    def cursor(self):
        return self.cursor_obj

    def transaction(self):
        connection = self

        class Transaction:
            def __enter__(self):
                connection.transaction_entries += 1

            def __exit__(self, *_args):
                return False

        return Transaction()


def test_invalidate_artist_promoter_jobs_marks_matching_jobs_failed():
    connection = FakeConnection(
        rows=[
            {"id": "job-1", "user_id": 1, "status": "failed"},
            {"id": "job-2", "user_id": 1, "status": "failed"},
        ]
    )

    rows = invalidate_artist_promoter_jobs(
        connection,
        artist_id=2178,
        error_message="artist biography refreshed; promoter recommendation job invalidated",
    )

    assert rows == [
        {"id": "job-1", "user_id": 1, "status": "failed"},
        {"id": "job-2", "user_id": 1, "status": "failed"},
    ]
    assert connection.transaction_entries == 1
    sql, params = connection.cursor_obj.executed[0]
    assert "job_type = %s" in sql
    assert "status IN ('queued', 'running')" in sql
    assert params == (
        "artist biography refreshed; promoter recommendation job invalidated",
        2178,
        "artist_promoters",
    )
