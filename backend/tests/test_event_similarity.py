from app.event_similarity import event_extracted_genres_by_id


class FakeCursor:
    def __init__(self):
        self.last_query = ""
        self.last_params = None
        self.view_rows = []
        self.raw_rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, query, params=None):
        self.last_query = " ".join(query.split())
        self.last_params = params

    def fetchone(self):
        if "to_regclass('public.event_extracted_genres')" in self.last_query:
            return {"table_name": "event_extracted_genres"}
        raise AssertionError(f"Unexpected fetchone query: {self.last_query}")

    def fetchall(self):
        if "FROM event_extracted_tags" in self.last_query:
            return self.view_rows
        if "FROM events e" in self.last_query:
            return self.raw_rows
        raise AssertionError(f"Unexpected fetchall query: {self.last_query}")


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()

    def cursor(self):
        return self.cursor_instance


def test_event_extracted_genres_prefers_saved_tags_and_falls_back_per_missing_event():
    connection = FakeConnection()
    connection.cursor_instance.view_rows = [
        {"event_id": 1, "tag_type": "style", "tag_value": "dark disco", "confidence": 0.9},
        {"event_id": 1, "tag_type": "genre", "tag_value": "ebm", "confidence": 0.9},
    ]
    connection.cursor_instance.raw_rows = [
        {
            "id": 2,
            "title": "Techno Night",
            "description_text": "A techno night with DJ set.",
            "lineup_raw": "",
            "lineup_residual_text": "",
        }
    ]

    styles_by_event_id = event_extracted_genres_by_id(connection, [1, 2])

    assert styles_by_event_id[1] == {"dark disco", "ebm"}
    assert styles_by_event_id[2] == {"techno"}
