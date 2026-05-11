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
