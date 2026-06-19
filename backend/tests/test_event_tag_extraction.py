import pytest

from app.event_tag_extraction import (
    EventSourceFields,
    EventTag,
    EventTagExtractionConfig,
    canonical_event_style_tags,
    event_batch_user_prompt,
    event_user_prompt,
    finalize_event_tags,
    merge_event_styles_and_metadata,
    parse_event_tags_response,
)
from app.event_tag_taxonomy import canonicalize_event_tag


def test_event_extractor_key_is_v3_because_v2_rows_exist():
    assert (
        EventTagExtractionConfig(model="gpt-test").extractor_key
        == "llm_event_tags_v3:openai:chat_completions:gpt-test"
    )


def test_event_user_prompt_mentions_only_mood_and_theme():
    prompt = event_user_prompt("A Night", "safe and inclusive", 6)
    assert "mood|theme" in prompt


def test_event_batch_user_prompt_mentions_only_mood_and_theme():
    prompt = event_batch_user_prompt(
        [{"id": 1, "name": "A Night", "text": "safe and inclusive"}],
        6,
    )
    assert "mood|theme" in prompt


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("playful immersive", ["playful", "immersive"]),
        ("floor focused", ["floor-focused"]),
        ("high energy", ["energetic"]),
    ],
)
def test_mood_canonicalization(value, expected):
    assert canonicalize_event_tag("mood", value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("safe space", ["safer-space"]),
        ("lgbtqia+ friendly", ["lgbtq"]),
        ("all-FLINTA lineup", ["flinta"]),
        ("consent culture", ["consent"]),
    ],
)
def test_theme_canonicalization(value, expected):
    assert canonicalize_event_tag("theme", value) == expected


@pytest.mark.parametrize(
    "evidence",
    [
        "live set by Artist",
        "Artist performs live",
        "hardware live act",
    ],
)
def test_unknown_tag_types_are_rejected_by_parser(evidence):
    tags = parse_event_tags_response(
        {
            "tags": [
                {"type": "noise", "value": "live", "confidence": 1.0, "evidence": evidence},
                {
                    "type": "theme",
                    "value": "queer",
                    "confidence": 1.0,
                    "evidence": "queer event for the local community",
                },
            ]
        },
        max_tags=12,
        event_text=f"{evidence} queer event for the local community",
    )
    assert [(tag.tag_type, tag.tag_value) for tag in tags] == [
        ("theme", "community"),
        ("theme", "queer"),
    ]


def test_merge_event_styles_and_metadata_keeps_styles_and_metadata():
    merged = merge_event_styles_and_metadata(
        "dark disco and techno",
        [EventTag("theme", "queer", 0.9, "queer event"), EventTag("mood", "energetic", 0.9, "energetic")],
        max_tags=12,
        sources=EventSourceFields(
            title="A Night",
            description="dark disco and techno",
            lineup_text="Artist A",
            structured_genres=("Techno",),
            artist_names=("Artist A",),
        ),
    )

    assert ("style", "dark disco") in [(tag.tag_type, tag.tag_value) for tag in merged]
    assert ("theme", "queer") in [(tag.tag_type, tag.tag_value) for tag in merged]
    assert ("mood", "energetic") in [(tag.tag_type, tag.tag_value) for tag in merged]


def test_canonical_event_style_tags_extracts_styles():
    tags = canonical_event_style_tags(
        sources=EventSourceFields(
            title="A Night",
            description="leftfield electro and bass",
            lineup_text="",
            structured_genres=("Techno",),
            artist_names=(),
        )
    )
    assert any(tag.tag_type == "style" for tag in tags)


def test_finalize_event_tags_enforces_per_type_limits():
    tags = finalize_event_tags(
        [
            EventTag("style", f"style-{index}", 1.0, f"evidence-{index}")
            for index in range(10)
        ]
        + [
            EventTag("theme", f"theme-{index}", 1.0, f"evidence-{index}")
            for index in range(10)
        ]
        + [
            EventTag("mood", f"mood-{index}", 1.0, f"evidence-{index}")
            for index in range(10)
        ],
        max_tags=12,
    )

    counts = {}
    for tag in tags:
        counts[tag.tag_type] = counts.get(tag.tag_type, 0) + 1

    assert counts["style"] <= 6
    assert counts["theme"] <= 4
    assert counts["mood"] <= 3
