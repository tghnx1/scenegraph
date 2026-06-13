from scripts.normalize_existing_artist_style_tags import (
    CLEANUP_EXTRACTOR,
    apply_style_cleanup,
    build_style_cleanup_plan,
    execute_style_cleanup,
)


def test_cleanup_plan_collapses_variants_and_reports_unknowns():
    plans = build_style_cleanup_plan(
        [
            {
                "artist_id": 1,
                "tag_value": "dnb",
                "confidence": 0.8,
                "evidence": None,
            },
            {
                "artist_id": 1,
                "tag_value": "drum & bass",
                "confidence": 0.9,
                "evidence": "best",
            },
            {
                "artist_id": 1,
                "tag_value": "sensual deep electric",
                "confidence": 1.0,
                "evidence": "unknown",
            },
        ]
    )

    assert len(plans) == 1
    assert [(row.tag_value, row.confidence, row.evidence) for row in plans[0].canonical_rows] == [
        ("drum and bass", 0.9, "best")
    ]
    assert plans[0].rejected_values == ("sensual deep electric",)


def test_cleanup_plan_suppresses_parent_styles():
    plans = build_style_cleanup_plan(
        [
            {"artist_id": 1, "tag_value": "techno", "confidence": 0.9, "evidence": None},
            {"artist_id": 1, "tag_value": "deep techno", "confidence": 0.8, "evidence": None},
        ]
    )

    assert [row.tag_value for row in plans[0].canonical_rows] == ["deep techno"]


class FakeCursor:
    def __init__(self):
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, query, params=None):
        self.executed.append((" ".join(query.split()), params))


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.transaction_entries = 0

    def cursor(self):
        return self.cursor_instance

    def transaction(self):
        connection = self

        class Transaction:
            def __enter__(self):
                connection.transaction_entries += 1

            def __exit__(self, *_args):
                return None

        return Transaction()


def test_cleanup_apply_only_deletes_style_rows_and_inserts_canonical_rows():
    connection = FakeConnection()
    plans = build_style_cleanup_plan(
        [{"artist_id": 1, "tag_value": "d&b", "confidence": 0.9, "evidence": "bio"}]
    )

    apply_style_cleanup(connection, plans)

    delete_sql, delete_params = connection.cursor_instance.executed[0]
    insert_sql, insert_params = connection.cursor_instance.executed[1]
    assert "tag_type = 'style'" in delete_sql
    assert delete_params == (1,)
    assert "INSERT INTO artist_extracted_tags" in insert_sql
    assert insert_params[1] == "drum and bass"
    assert insert_params[4] == CLEANUP_EXTRACTOR


def test_cleanup_dry_run_does_not_execute_writes():
    connection = FakeConnection()
    plans = build_style_cleanup_plan(
        [{"artist_id": 1, "tag_value": "dnb", "confidence": 0.9, "evidence": None}]
    )

    execute_style_cleanup(connection, plans, apply=False)

    assert connection.cursor_instance.executed == []
    assert connection.transaction_entries == 0


def test_cleanup_apply_runs_in_one_transaction():
    connection = FakeConnection()
    plans = build_style_cleanup_plan(
        [{"artist_id": 1, "tag_value": "dnb", "confidence": 0.9, "evidence": None}]
    )

    execute_style_cleanup(connection, plans, apply=True)

    assert connection.transaction_entries == 1
    assert connection.cursor_instance.executed
