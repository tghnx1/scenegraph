from app.schema_preflight import OPTIONAL_TABLES, REQUIRED_TABLES


def test_manual_artist_connections_table_is_required():
    assert "artist_manual_connections" in REQUIRED_TABLES
    assert "artist_manual_connections" not in OPTIONAL_TABLES
