from app.event_tag_extraction import (
    EventTag,
    EventTagExtractionConfig,
    event_batch_user_prompt,
    event_user_prompt,
    merge_event_styles_and_metadata,
    parse_event_tags_response,
)


def test_event_extractor_key_is_v2():
    assert (
        EventTagExtractionConfig(model="gpt-test").extractor_key
        == "llm_event_tags_v2:openai:chat_completions:gpt-test"
    )


def test_event_llm_style_items_are_ignored_but_non_styles_remain():
    tags = parse_event_tags_response(
        {
            "tags": [
                {"type": "style", "value": "sensual deep electric", "confidence": 1.0},
                {"type": "style", "value": "dnb", "confidence": 1.0},
                {"type": "format", "value": "DJ set", "confidence": 0.9},
                {"type": "mood", "value": "Hypnotic", "confidence": 0.8},
            ]
        },
        max_tags=10,
    )

    assert [(tag.tag_type, tag.tag_value) for tag in tags] == [
        ("format", "dj set"),
        ("mood", "hypnotic"),
    ]


def test_event_styles_come_from_shared_dictionary():
    tags = merge_event_styles_and_metadata(
        "A dark disco and drum n bass night",
        [EventTag("format", "dj set", 0.9)],
        max_tags=10,
    )

    assert [(tag.tag_type, tag.tag_value) for tag in tags] == [
        ("style", "dark disco"),
        ("style", "drum and bass"),
        ("format", "dj set"),
    ]


def test_single_and_batch_event_prompts_share_strict_rules():
    single = event_user_prompt("Night", "Text", 10)
    batch = event_batch_user_prompt([{"id": 1, "name": "Night", "text": "Text"}], 10)

    for prompt in (single, batch):
        assert "Do not extract musical styles or genres" in prompt
        assert "ticket, price, venue amenity, dress-code, date, or access" in prompt
        assert '"type": "format|mood|theme|instrumentation|series"' in prompt
