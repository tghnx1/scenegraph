import pytest

from app.style_tags import canonicalize_style_tags, extract_style_tags, style_overlap_score


@pytest.mark.parametrize(
    "value",
    [
        "drum n bass",
        "drum 'n' bass",
        "drum n' bass",
        "drum & bass",
        "dnb",
        "d&b",
    ],
)
def test_canonicalize_drum_and_bass_aliases(value):
    assert canonicalize_style_tags(value) == ["drum and bass"]


@pytest.mark.parametrize("value", ["Zielińska", "Kościuszko", "Škabrnja"])
def test_style_alias_boundaries_are_unicode_safe(value):
    assert canonicalize_style_tags(value) == []


@pytest.mark.parametrize("value", ["Ska night", "ska, punk and reggae"])
def test_unicode_safe_boundaries_keep_real_ska_mentions(value):
    assert "ska" in canonicalize_style_tags(value)


def test_hi_nrg_does_not_treat_high_energy_as_a_style():
    assert canonicalize_style_tags("a high-energy set") == []
    assert canonicalize_style_tags("Hi-NRG night") == ["hi-nrg"]


def test_canonicalize_multiple_styles_and_suppress_parents():
    assert canonicalize_style_tags("Dark Disco, EBM and Electro") == [
        "dark disco",
        "ebm",
        "electro",
    ]
    assert canonicalize_style_tags("deep techno and techno") == ["deep techno"]


@pytest.mark.parametrize(
    "value",
    [
        "deep raw essential",
        "sensual deep electric",
        "reversed revolution",
        "latex",
        "leather",
        "performance",
        "live",
    ],
)
def test_canonicalize_unknown_descriptions_returns_empty(value):
    assert canonicalize_style_tags(value) == []


def test_extract_style_tags_from_artist_biography():
    tags = extract_style_tags(
        "Slow-burning electronics shaped by dark disco, acid, electro, and EBM. "
        "The sound moves between acid techno and industrial."
    )

    assert tags == ["acid techno", "dark disco", "ebm", "electro", "industrial"]


def test_style_overlap_score_uses_jaccard_similarity():
    assert style_overlap_score(["dark disco", "ebm"], ["ebm", "techno"]) == 1 / 3
    assert style_overlap_score(
        ["dark disco", "ebm", "italo", "new wave"],
        ["dark disco", "ebm"],
    ) == 0.5
    assert style_overlap_score(["a", "b", "c", "d"], ["a", "b", "c", "d"]) == 1.0
    assert style_overlap_score([], ["ebm"]) == 0.0


def test_extract_style_tags_keeps_new_wave_without_generic_wave():
    tags = extract_style_tags("Italo, Dark Disco, EBM, New Wave, Indie Dance.")

    assert tags == ["dark disco", "ebm", "indie dance", "italo", "new wave"]


def test_extract_style_tags_covers_broader_electronic_styles():
    tags = extract_style_tags(
        "A set moving through coldwave, minimal wave, new beat, body music, "
        "industrial techno, nu-disco, UKG, jungle and drum & bass."
    )

    assert tags == [
        "cold wave",
        "drum and bass",
        "ebm",
        "industrial techno",
        "jungle",
        "minimal wave",
        "new beat",
        "nu disco",
        "uk garage",
    ]


def test_extract_style_tags_prefers_specific_styles_over_parent_matches():
    tags = extract_style_tags(
        "Dark disco, acid house, deep techno, synthwave, progressive trance, electro house."
    )

    assert tags == [
        "acid house",
        "dark disco",
        "deep techno",
        "electro house",
        "progressive trance",
        "synthwave",
    ]


def test_extract_style_tags_covers_non_electronic_genres():
    tags = extract_style_tags(
        "A night of hip-hop, rap, trap, r&b, neo soul, jazz, reggae, dancehall, "
        "ska, indie rock, punk and death metal."
    )

    assert tags == [
        "dancehall",
        "death metal",
        "hip hop",
        "indie rock",
        "jazz",
        "neo soul",
        "punk",
        "r&b",
        "rap",
        "reggae",
        "ska",
        "trap",
    ]
