import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql://scenegraph:change-me@db:5432/scenegraph")
sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts.import_events import normalize_lineup_text


def test_normalize_lineup_text_keeps_only_residual_context():
    raw = """
    <artist id="63943">Isabeau Fort</artist>
    [Laut & Luise / &&]

    Cem Gemalmaz

    <artist id="131590">Kahl & Kæmena</artist> *live

    <artist id="127722">Noy Ära</artist>

    Coco Loris
    """

    assert normalize_lineup_text(raw) == "\n".join(
        [
            "[Laut & Luise / &&]",
            "Cem Gemalmaz",
            "Kahl & Kæmena live",
            "Coco Loris",
        ]
    )


def test_normalize_lineup_text_preserves_b2b_between_tagged_artists():
    raw = '<artist id="1">A</artist> b2b <artist id="2">B</artist>'

    assert normalize_lineup_text(raw) == "A b2b B"


def test_normalize_lineup_text_drops_tagged_artist_without_context():
    raw = '<artist id="1">Known Artist</artist>\nPlain Artist'

    assert normalize_lineup_text(raw) == "Plain Artist"


def test_normalize_lineup_text_drops_zero_width_only_residuals():
    raw = '<artist id="1">Known Artist</artist>\n\u2060\u2060'

    assert normalize_lineup_text(raw) is None


def test_normalize_lineup_text_drops_empty_time_slots_and_keeps_timed_artists():
    raw = """
    ▣▣▣ MAIN ▣▣▣
    22:00-00:30 <artist id="1">Known Artist</artist>
    00:30-03:00 Plain Artist
    03:00-06:00 <artist id="2">A</artist> b2b <artist id="3">B</artist>
    """

    assert normalize_lineup_text(raw) == "\n".join(
        [
            "Plain Artist",
            "A b2b B",
        ]
    )


def test_normalize_lineup_text_drops_tba_headers_and_long_prose():
    raw = """
    tba
    more TBA
    SATURDAY
    AURORA BAR
    Get ready for our next nightrave on Thursday 2 April in ://about blank, where the spirit of the underground sounds of Amsterdam collide with the heart of Berlin!
    Unknown Artist
    """

    assert normalize_lineup_text(raw) == "Unknown Artist"


def test_normalize_lineup_text_drops_orphan_room_and_note_fragments():
    raw = """
    Schmiede:
    Lager:
    23:15-End <artist id="1">Known Artist</artist>
    .
    @
    (Chile)
    Choreographies by Sharon Eyal and Ohad Naharin
    Actual Artist
    """

    assert normalize_lineup_text(raw) == "Actual Artist"


def test_normalize_lineup_text_does_not_strip_connector_words_inside_names():
    raw = "Andre Wiesé, Felix"

    assert normalize_lineup_text(raw) == "Andre Wiesé, Felix"


def test_normalize_lineup_text_strips_role_prefixes_and_social_handle_marks():
    raw = """
    SHOW: ANESHA
    DJs: KÖNIGSMANN, TIASZ
    @VictorDiscos
    @Mellowman @
    IG@KIKIBERLIN2025
    """

    assert normalize_lineup_text(raw) == "\n".join(
        [
            "ANESHA",
            "KÖNIGSMANN, TIASZ",
            "VictorDiscos",
            "Mellowman",
            "IG@KIKIBERLIN2025",
        ]
    )


def test_normalize_lineup_text_drops_marketing_and_floor_headers():
    raw = """
    FREE ENTRY ALL DAY LONG
    Sunshine incoming, lets spend a splendid Saturday together with you on the dancefloor and our lovely beer garden!
    SATURDAY // OPEN AIR
    Open Air Floor | 15-21
    Open Decks for Vinyl DJs
    MONAMI
    """

    assert normalize_lineup_text(raw) == "MONAMI"


def test_normalize_lineup_text_removes_empty_connector_parentheses():
    raw = 'disk.drop (<artist id="1">Known A</artist> & <artist id="2">Known B</artist>)'

    assert normalize_lineup_text(raw) == "disk.drop"
