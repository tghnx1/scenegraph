import pytest

from app.artist_tag_extraction import (
    ArtistTag,
    TagExtractionConfig,
    batch_user_prompt,
    extract_responses_output_text,
    extract_json_object,
    is_content_filter_error,
    merge_artist_tags,
    normalize_tag_value,
    parse_artist_batch_response,
    parse_tags_response,
    split_biography_chunks,
    tag_extraction_text_hash,
)


def test_tag_extraction_config_reads_openai_env(monkeypatch):
    monkeypatch.setenv("EXTRACTION_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_EXTRACTION_MODEL", "gpt-4.1-nano")
    monkeypatch.setenv("ARTIST_TAG_EXTRACTION_MAX_TAGS", "12")

    config = TagExtractionConfig.from_env()

    assert config.provider == "openai"
    assert config.model == "gpt-4.1-nano"
    assert config.api == "chat_completions"
    assert config.max_tags == 12
    assert config.extractor_key == "llm_artist_tags_v2:openai:chat_completions:gpt-4.1-nano"


def test_tag_extraction_config_reads_azure_env(monkeypatch):
    monkeypatch.setenv("EXTRACTION_PROVIDER", "azure")
    monkeypatch.setenv("AZURE_OPENAI_EXTRACTION_DEPLOYMENT", "scenegraph-gpt-41-mini")

    config = TagExtractionConfig.from_env()

    assert config.provider == "azure"
    assert config.model == "scenegraph-gpt-41-mini"
    assert config.api == "chat_completions"
    assert (
        config.extractor_key
        == "llm_artist_tags_v2:azure:chat_completions:scenegraph-gpt-41-mini"
    )


def test_tag_extraction_config_reads_azure_responses_url(monkeypatch):
    monkeypatch.setenv("EXTRACTION_PROVIDER", "azure")
    monkeypatch.setenv(
        "AZURE_OPENAI_RESPONSES_URL",
        "https://example.cognitiveservices.azure.com/openai/responses?api-version=2025-04-01-preview",
    )
    monkeypatch.setenv("AZURE_OPENAI_RESPONSES_MODEL", "gpt-4.1-mini")
    monkeypatch.delenv("EXTRACTION_API", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_EXTRACTION_DEPLOYMENT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_CHAT_DEPLOYMENT", raising=False)
    monkeypatch.delenv("OPENAI_EXTRACTION_MODEL", raising=False)

    config = TagExtractionConfig.from_env()

    assert config.provider == "azure"
    assert config.api == "responses"
    assert config.model == "gpt-4.1-mini"
    assert config.azure_responses_url == (
        "https://example.cognitiveservices.azure.com/openai/responses?api-version=2025-04-01-preview"
    )
    assert config.extractor_key == "llm_artist_tags_v2:azure:responses:gpt-4.1-mini"


def test_tag_extraction_config_requires_azure_deployment(monkeypatch):
    monkeypatch.setenv("EXTRACTION_PROVIDER", "azure")
    monkeypatch.delenv("AZURE_OPENAI_EXTRACTION_DEPLOYMENT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_CHAT_DEPLOYMENT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_RESPONSES_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_EXTRACTION_MODEL", raising=False)

    with pytest.raises(ValueError, match="AZURE_OPENAI_EXTRACTION_DEPLOYMENT"):
        TagExtractionConfig.from_env()


def test_extract_json_object_handles_surrounding_text():
    payload = extract_json_object('Here: {"tags": [{"type": "style", "value": "EBM"}]}')

    assert payload == {"tags": [{"type": "style", "value": "EBM"}]}


def test_is_content_filter_error_detects_azure_messages():
    assert is_content_filter_error(RuntimeError("code: content_filter"))
    assert is_content_filter_error(RuntimeError("ResponsibleAIPolicyViolation"))
    assert not is_content_filter_error(RuntimeError("rate limit"))


def test_extract_responses_output_text_from_output_array():
    content = extract_responses_output_text(
        {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"tags": [{"type": "style", "value": "EBM"}]}',
                        }
                    ],
                }
            ]
        }
    )

    assert content == '{"tags": [{"type": "style", "value": "EBM"}]}'


def test_batch_user_prompt_includes_artist_ids():
    prompt = batch_user_prompt(
        [
            {"id": 2178, "name": "Holywanderer", "biography": "Dark Disco."},
            {"id": 42, "name": "Other", "biography": "Electro."},
        ],
        max_tags=4,
    )

    assert "Artist ID: 2178" in prompt
    assert "Artist ID: 42" in prompt
    assert '"artistId": 123' in prompt
    assert "Keep at most 4 tags per artist" in prompt


def test_parse_tags_response_normalizes_and_deduplicates():
    tags = parse_tags_response(
        {
            "tags": [
                {
                    "type": "style",
                    "value": " EBM ",
                    "confidence": 0.92,
                    "evidence": "EBM and dark disco",
                },
                {"type": "style", "value": "ebm", "confidence": 0.7},
                {"type": "label", "value": "Laut & Luise", "confidence": "0.8"},
                {"type": "unknown", "value": "drop me", "confidence": 1.0},
                {"type": "alias", "value": "Holywanderer", "confidence": 1.0},
            ]
        },
        artist_name="Holywanderer",
        max_tags=10,
    )

    assert [(tag.tag_type, tag.tag_value, tag.confidence) for tag in tags] == [
        ("style", "ebm", 0.92),
        ("label", "Laut & Luise", 0.8),
    ]
    assert tags[0].evidence == "EBM and dark disco"


def test_parse_tags_response_expands_and_deduplicates_canonical_styles():
    tags = parse_tags_response(
        {
            "tags": [
                {
                    "type": "style",
                    "value": "Dark Disco, EBM and drum n bass",
                    "confidence": 0.9,
                    "evidence": "explicit styles",
                },
                {"type": "style", "value": "d&b", "confidence": 0.8},
                {"type": "style", "value": "sensual deep electric", "confidence": 1.0},
            ]
        },
        artist_name="Artist",
        max_tags=10,
    )

    assert [(tag.tag_type, tag.tag_value, tag.confidence) for tag in tags] == [
        ("style", "dark disco", 0.9),
        ("style", "drum and bass", 0.9),
        ("style", "ebm", 0.9),
    ]
    assert all(tag.evidence == "explicit styles" for tag in tags)


def test_parse_tags_response_suppresses_parent_styles_across_llm_items():
    tags = parse_tags_response(
        {
            "tags": [
                {"type": "style", "value": "techno"},
                {"type": "style", "value": "deep techno"},
            ]
        },
        artist_name="Artist",
        max_tags=10,
    )

    assert [(tag.tag_type, tag.tag_value) for tag in tags] == [("style", "deep techno")]


def test_parse_tags_response_preserves_non_style_normalization():
    tags = parse_tags_response(
        {
            "tags": [
                {"type": "label", "value": "Laut & Luise Records"},
                {"type": "collective", "value": "The Holyberg Music Association"},
                {"type": "role", "value": "DJ"},
                {"type": "residency", "value": "Resident at Sameheads"},
                {"type": "alias", "value": "Other Name"},
            ]
        },
        artist_name="Artist",
        max_tags=10,
    )

    assert [(tag.tag_type, tag.tag_value) for tag in tags] == [
        ("label", "Laut & Luise"),
        ("collective", "Holyberg"),
        ("role", "dj"),
        ("residency", "Sameheads"),
        ("alias", "Other Name"),
    ]


def test_parse_artist_batch_response_normalizes_by_artist_id():
    results = parse_artist_batch_response(
        {
            "artists": [
                {
                    "artistId": 2178,
                    "tags": [
                        {"type": "style", "value": "Dark Disco"},
                        {"type": "collective", "value": "Holyberg music association"},
                        {"type": "label", "value": "Bandcamp"},
                        {"type": "residency", "value": "Berlin"},
                    ],
                },
                {"artistId": 9999, "tags": [{"type": "style", "value": "drop me"}]},
                {"artistId": "bad", "tags": [{"type": "style", "value": "drop me"}]},
            ]
        },
        artists=[{"id": 2178, "name": "Holywanderer"}],
        max_tags=10,
    )

    assert list(results) == [2178]
    assert [(tag.tag_type, tag.tag_value) for tag in results[2178]] == [
        ("style", "dark disco"),
        ("collective", "Holyberg"),
    ]


def test_parse_tags_response_deduplicates_canonical_scene_entities():
    tags = parse_tags_response(
        {
            "tags": [
                {"type": "collective", "value": "Holyberg music association"},
                {"type": "collective", "value": "holyberg"},
            ]
        },
        artist_name="Holywanderer",
        max_tags=10,
    )

    assert [(tag.tag_type, tag.tag_value) for tag in tags] == [("collective", "Holyberg")]


def test_merge_artist_tags_deduplicates_and_keeps_highest_confidence():
    tags = merge_artist_tags(
        [
            [
                ArtistTag("style", "ebm", 0.5, "first"),
                ArtistTag("role", "dj", 1.0),
            ],
            [
                ArtistTag("style", "EBM", 0.9, "better"),
                ArtistTag("style", "dark disco", 0.8),
            ],
        ],
        max_tags=2,
    )

    assert [(tag.tag_type, tag.tag_value, tag.confidence, tag.evidence) for tag in tags] == [
        ("style", "EBM", 0.9, "better"),
        ("role", "dj", 1.0, None),
    ]


def test_parse_tags_response_caps_to_max_tags():
    tags = parse_tags_response(
        {
            "tags": [
                {"type": "style", "value": "dark disco"},
                {"type": "style", "value": "ebm"},
            ]
        },
        artist_name="Artist",
        max_tags=1,
    )

    assert len(tags) == 1
    assert tags[0].tag_value == "dark disco"


def test_normalize_tag_value_preserves_label_case():
    assert normalize_tag_value("label", "  Laut & Luise /  ") == "Laut & Luise"
    assert normalize_tag_value("style", "  Dark Disco  ") == "dark disco"


def test_normalize_tag_value_canonicalizes_scene_entities():
    assert normalize_tag_value("collective", "  holyberg music association ") == "holyberg"
    assert normalize_tag_value("collective", "The Holyberg Music Association") == "Holyberg"
    assert normalize_tag_value("collective", "member of the Holyberg music association") == "Holyberg"
    assert normalize_tag_value("label", "Laut & Luise Records") == "Laut & Luise"
    assert normalize_tag_value("label", "Music From Memory") == "Music From Memory"
    assert normalize_tag_value("residency", "The Bunker New York") == "The Bunker New York"
    assert normalize_tag_value("residency", "MatreshkaBerlin resident") == "MatreshkaBerlin"
    assert normalize_tag_value("residency", "Resident at Sameheads") == "Sameheads"


def test_split_biography_chunks_covers_text_with_bounded_chunks():
    text = (
        "Biography: First sentence about dark disco. "
        "Second sentence about EBM and labels. "
        "Third sentence is intentionally longer than the previous two so it should be moved."
    )

    chunks = split_biography_chunks(text, max_chars=80)

    assert all(len(chunk) <= 80 for chunk in chunks)
    assert " ".join(chunks) == text.replace("Biography: ", "")


def test_tag_extraction_text_hash_normalizes_biography():
    assert tag_extraction_text_hash("Biography:  Dark\nDisco") == tag_extraction_text_hash(
        "Dark Disco"
    )
