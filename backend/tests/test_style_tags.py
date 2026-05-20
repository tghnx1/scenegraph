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
