from app.style_tags import extract_style_tags, style_overlap_score


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
