import json
from io import StringIO

import pytest

import app.event_tag_extraction as extraction
from app.event_style_tags import extract_event_style_matches
from app.event_tag_extraction import (
    EventSourceFields,
    EventTag,
    EventTagExtractionConfig,
    canonical_event_style_tags,
    event_batch_user_prompt,
    event_user_prompt,
    extract_event_tag_batch_with_llm,
    extract_event_tags_with_chunked_fallback,
    extract_event_tags_with_llm,
    fetch_event_texts,
    finalize_event_tags,
    merge_event_styles_and_metadata,
    parse_event_tags_response,
)
from app.event_tag_taxonomy import (
    canonicalize_event_tag,
    canonicalize_series,
    repeated_series_title_roots,
)
from scripts.extract_event_tags import (
    event_tags_json_line,
    output_or_persist_event_tags,
    print_completion_summary,
)


def test_event_extractor_key_is_v3_because_v2_rows_exist():
    assert (
        EventTagExtractionConfig(model="gpt-test").extractor_key
        == "llm_event_tags_v3:openai:chat_completions:gpt-test"
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("live set", ["live"]),
        ("live act", ["live"]),
        ("live pa", ["live"]),
        ("back-to-backs", ["b2b"]),
        ("DJ sets", ["dj-set"]),
        ("club night", ["club-night"]),
        ("klubnacht", ["club-night"]),
    ],
)
def test_format_canonicalization(value, expected):
    assert canonicalize_event_tag("format", value) == expected


@pytest.mark.parametrize("value", ["free entry", "two floors", "chill area", "residents"])
def test_format_rejects_access_and_venue_metadata(value):
    assert canonicalize_event_tag("format", value) == []


@pytest.mark.parametrize(
    "evidence",
    [
        "live liquid visuals",
        "live projection",
        "live stream",
        "live broadcast",
        "live and direct airing",
    ],
)
def test_format_live_rejects_non_performance_evidence(evidence):
    tags = parse_event_tags_response(
        {"tags": [{"type": "format", "value": "live", "confidence": 1.0, "evidence": evidence}]},
        max_tags=12,
        event_text=evidence,
    )
    assert tags == []


@pytest.mark.parametrize(
    "evidence",
    [
        "live set by Artist",
        "Artist performs live",
        "hardware live act",
        "Artist (live)",
    ],
)
def test_format_live_accepts_music_performance_evidence(evidence):
    tags = parse_event_tags_response(
        {"tags": [{"type": "format", "value": "live", "confidence": 1.0, "evidence": evidence}]},
        max_tags=12,
        event_text=evidence,
    )
    assert [(tag.tag_type, tag.tag_value) for tag in tags] == [("format", "live")]


@pytest.mark.parametrize("evidence", ["to showcase new work", "will showcase the artist"])
def test_format_showcase_rejects_verb_evidence(evidence):
    tags = parse_event_tags_response(
        {
            "tags": [
                {"type": "format", "value": "showcase", "confidence": 1.0, "evidence": evidence}
            ]
        },
        max_tags=12,
        event_text=evidence,
    )
    assert tags == []


@pytest.mark.parametrize("evidence", ["label showcase", "artist showcase night"])
def test_format_showcase_accepts_event_noun_evidence(evidence):
    tags = parse_event_tags_response(
        {
            "tags": [
                {"type": "format", "value": "showcase", "confidence": 1.0, "evidence": evidence}
            ]
        },
        max_tags=12,
        event_text=evidence,
    )
    assert [(tag.tag_type, tag.tag_value) for tag in tags] == [("format", "showcase")]


def test_mood_canonicalization_splits_composites():
    assert canonicalize_event_tag("mood", "playful immersive") == ["playful", "immersive"]
    assert canonicalize_event_tag("mood", "floor focused") == ["floor-focused"]


@pytest.mark.parametrize("value", ["safe space", "honest and personal", "queer friendly"])
def test_mood_rejects_policy_and_marketing_values(value):
    assert canonicalize_event_tag("mood", value) == []


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("safe space", ["safer-space"]),
        ("safer spaces", ["safer-space"]),
        ("lgbtqia+ friendly", ["lgbtq"]),
        ("anti discrimination", ["anti-discrimination"]),
        ("consent culture", ["consent"]),
    ],
)
def test_theme_canonicalization(value, expected):
    assert canonicalize_event_tag("theme", value) == expected


def test_theme_canonicalization_expands_atomic_values():
    assert set(canonicalize_event_tag("theme", "bipoc queer flinta safe space")) == {
        "bipoc",
        "queer",
        "flinta",
        "safer-space",
    }


@pytest.mark.parametrize(
    "evidence",
    [
        "co-founder of BIPOC Yoko Yoko",
        "curates inclusive events",
        "founder of a FLINTA agency",
    ],
)
def test_theme_rejects_biography_only_evidence(evidence):
    tags = parse_event_tags_response(
        {"tags": [{"type": "theme", "value": evidence, "confidence": 1.0, "evidence": evidence}]},
        max_tags=12,
        event_text=evidence,
    )
    assert tags == []


@pytest.mark.parametrize(
    ("value", "evidence", "expected"),
    [
        ("bipoc", "a BIPOC-focused event", "bipoc"),
        ("inclusive", "an inclusive party", "inclusive"),
        ("flinta", "FLINTA guests are welcome", "flinta"),
        ("flinta", "all-FLINTA lineup", "flinta"),
    ],
)
def test_theme_accepts_event_level_evidence(value, evidence, expected):
    tags = parse_event_tags_response(
        {"tags": [{"type": "theme", "value": value, "confidence": 1.0, "evidence": evidence}]},
        max_tags=12,
        event_text=evidence,
    )
    assert [(tag.tag_type, tag.tag_value) for tag in tags] == [("theme", expected)]


def test_theme_composite_evidence_expands_all_atomic_values():
    sex_positive = "sex-positive and LGBTQIA+ friendly party"
    protected = "protected space for BIPOC, Queer & FLINTA guests"
    sex_positive_tags = parse_event_tags_response(
        {
            "tags": [
                {
                    "type": "theme",
                    "value": "sex-positive",
                    "confidence": 1.0,
                    "evidence": sex_positive,
                }
            ]
        },
        max_tags=12,
        event_text=sex_positive,
    )
    protected_tags = parse_event_tags_response(
        {
            "tags": [
                {
                    "type": "theme",
                    "value": "bipoc",
                    "confidence": 1.0,
                    "evidence": protected,
                }
            ]
        },
        max_tags=12,
        event_text=protected,
    )
    assert {tag.tag_value for tag in sex_positive_tags} == {"sex-positive", "lgbtq"}
    assert {tag.tag_value for tag in protected_tags} == {
        "safer-space",
        "bipoc",
        "queer",
        "flinta",
    }


@pytest.mark.parametrize(
    "value",
    [
        "collaboration between artists crews and collectives",
        "support your local dyke record store",
        "spring full moon gathering",
        "borders and conflict",
        "fusion of tradition and technology",
    ],
)
def test_theme_rejects_event_specific_prose(value):
    assert canonicalize_event_tag("theme", value) == []


def test_instrumentation_canonicalization_splits_composites():
    assert canonicalize_event_tag("instrumentation", "keyboards and percussion") == [
        "keyboards",
        "percussion",
    ]
    assert canonicalize_event_tag("instrumentation", "cdjs and turntables") == [
        "turntables",
        "cdj",
    ]


@pytest.mark.parametrize(
    "value",
    ["motion tracking", "projection", "spatial sound system", "live performance"],
)
def test_instrumentation_rejects_visual_and_format_values(value):
    assert canonicalize_event_tag("instrumentation", value) == []


def test_series_requires_recurrence_and_removes_edition_metadata():
    assert canonicalize_series(
        "Gather in Sound Vol. 4",
        title="Gather in Sound Vol. 4",
        evidence="Gather in Sound Vol. 4",
    ) == ["gather in sound"]
    assert canonicalize_series(
        "Push Play Peach Edition",
        title="Push Play Peach Edition",
        evidence="Push Play Peach Edition",
    ) == ["push play"]
    assert canonicalize_series(
        "Pleasure Patterns Opening Party",
        title="Pleasure Patterns Opening Party",
        evidence="Pleasure Patterns Opening Party",
    ) == []
    assert canonicalize_series(
        "Every Thursday",
        title="Weekly night",
        evidence="Every Thursday",
    ) == []


@pytest.mark.parametrize(
    ("value", "title", "evidence"),
    [
        ("Casadephunk", "Renate Klubnacht w/ Casadephunk", "GREEN hosted by Casadephunk"),
        (
            "Analogue Foundation",
            "Analogue Foundation presents Laurel Halo",
            "Analogue Foundation presents",
        ),
        ("Zu mir oder zu dir", "The Unknown", "Every Thursday @ Zu mir oder zu dir"),
    ],
)
def test_series_rejects_hosts_promoters_and_venues(value, title, evidence):
    assert canonicalize_series(value, title=title, evidence=evidence) == []


@pytest.mark.parametrize(
    ("value", "title", "evidence", "expected"),
    [
        ("Gather in Sound Vol. 4", "Gather in Sound Vol. 4", "Gather in Sound Vol. 4", "gather in sound"),
        ("Push Play Peach Edition", "Push Play — Peach Edition", "Push Play Peach Edition", "push play"),
        ("Signals", "Signals", "monthly Signals series", "signals"),
    ],
)
def test_series_accepts_independent_recurring_identity(value, title, evidence, expected):
    assert canonicalize_series(value, title=title, evidence=evidence) == [expected]


def test_event_llm_style_items_are_ignored_and_metadata_is_canonicalized():
    tags = parse_event_tags_response(
        {
            "tags": [
                {"type": "style", "value": "dnb", "confidence": 1.0, "evidence": "dnb"},
                {"type": "format", "value": "DJ sets", "confidence": 0.9, "evidence": "DJ sets"},
                {"type": "mood", "value": "Hypnotic", "confidence": 0.8, "evidence": "Hypnotic"},
            ]
        },
        max_tags=10,
        event_text="Hypnotic DJ sets and dnb.",
    )

    assert [(tag.tag_type, tag.tag_value) for tag in tags] == [
        ("format", "dj-set"),
        ("mood", "hypnotic"),
    ]


def test_llm_metadata_requires_supported_non_empty_evidence():
    tags = parse_event_tags_response(
        {
            "tags": [
                {"type": "format", "value": "DJ set", "confidence": 1.0},
                {"type": "mood", "value": "hypnotic", "confidence": 1.0, "evidence": "invented"},
            ]
        },
        max_tags=10,
        event_text="A DJ set.",
    )
    assert tags == []


def test_llm_metadata_rejects_evidence_that_does_not_support_value():
    tags = parse_event_tags_response(
        {
            "tags": [
                {
                    "type": "theme",
                    "value": "safe space",
                    "confidence": 1.0,
                    "evidence": "Any energy that disrupts this peace will be removed",
                },
                {
                    "type": "format",
                    "value": "DJ set",
                    "confidence": 1.0,
                    "evidence": "Alice, Bob, Charlie",
                },
            ]
        },
        max_tags=10,
        event_text="Any energy that disrupts this peace will be removed. Alice, Bob, Charlie.",
    )
    assert tags == []


def test_event_style_false_positives_are_rejected():
    assert extract_event_style_matches(title="Chantal's House of Shame") == []
    assert extract_event_style_matches(description="the bass player joined the band") == []
    assert extract_event_style_matches(description="rolling percussion and a driving bass as the club thrives") == []
    assert extract_event_style_matches(description="metal accessories are required") == []


def test_event_style_rejects_dnb_audio_brand_but_keeps_music_uses():
    assert extract_event_style_matches(description="d&b audiotechnik spatial sound system") == []
    for text in ("d&b night", "drum & bass set", "DNB and jungle"):
        assert any(match.value == "drum and bass" for match in extract_event_style_matches(description=text))


@pytest.mark.parametrize(
    "text",
    [
        "Need a break from techno?",
        "not techno",
        "no techno",
        "without techno",
        "instead of techno",
        "alternative to techno",
        "far from techno",
        "anything but techno",
    ],
)
def test_event_style_rejects_negated_mentions(text):
    assert extract_event_style_matches(description=text) == []


def test_event_style_keeps_positive_mention_after_negated_one():
    matches = extract_event_style_matches(
        description="Need a break from techno? Techno returns to the main floor."
    )
    assert [match.value for match in matches] == ["techno"]


def test_ambiguous_funk_requires_music_context_across_languages():
    assert extract_event_style_matches(description="per Funk die Security rufen") == []
    assert extract_event_style_matches(description="via Funk erreichbar") == []
    assert extract_event_style_matches(description="Funkgerät an der Tür") == []
    assert [match.value for match in extract_event_style_matches(description="Funk Musik Nacht")] == [
        "funk"
    ]


@pytest.mark.parametrize("artist_name", ["Tribal Goblin", "Housemeister", "Metallica", "(c)rave"])
def test_artist_names_are_removed_before_event_style_matching(artist_name):
    assert extract_event_style_matches(title=artist_name, artist_names=[artist_name]) == []


def test_single_word_title_style_requires_music_context():
    assert extract_event_style_matches(title="Experimental Broadcast") == []
    assert [match.value for match in extract_event_style_matches(title="Ska night")] == ["ska"]
    assert [match.value for match in extract_event_style_matches(title="Techno")] == ["techno"]


def test_descriptive_lineup_context_still_produces_styles_after_artist_removal():
    matches = extract_event_style_matches(
        lineup_text="Tribal Goblin performs a tribal techno set",
        artist_names=["Tribal Goblin"],
    )
    assert [match.value for match in matches] == ["tribal techno"]


def test_event_styles_accept_explicit_context_and_structured_genres():
    description = extract_event_style_matches(description="a deep house and techno night")
    structured = extract_event_style_matches(structured_genres=["House"])

    assert [(match.value, match.source) for match in description] == [
        ("deep house", "description"),
        ("techno", "description"),
    ]
    assert all("deep house and techno night" in match.evidence for match in description)
    assert [(match.value, match.evidence, match.source) for match in structured] == [
        ("house", "House", "structured_genre")
    ]
    assert extract_event_style_matches(description="house music all night")[0].value == "house"


def test_every_deterministic_style_has_source_evidence():
    tags = canonical_event_style_tags(
        sources=EventSourceFields(
            description="A drum n bass night",
            structured_genres=("House",),
        )
    )
    assert {(tag.tag_value, tag.evidence) for tag in tags} == {
        ("drum and bass", "description: A drum n bass night"),
        ("house", "structured_genre: House"),
    }
    assert all(tag.evidence for tag in tags)


def test_event_styles_and_metadata_merge_uses_shared_dictionary():
    tags = merge_event_styles_and_metadata(
        "A dark disco and drum n bass night",
        [EventTag("format", "dj-set", 0.9, "DJ set")],
        max_tags=10,
    )

    assert [(tag.tag_type, tag.tag_value) for tag in tags] == [
        ("style", "dark disco"),
        ("style", "drum and bass"),
        ("format", "dj-set"),
    ]


def test_final_limits_are_applied_after_merge():
    tags = []
    for index in range(10):
        tags.append(EventTag("style", f"style-{index}", 1.0, f"description: style-{index}"))
    for tag_type, count in (
        ("format", 6),
        ("mood", 6),
        ("theme", 6),
        ("instrumentation", 8),
        ("series", 3),
    ):
        for index in range(count):
            tags.append(EventTag(tag_type, f"{tag_type}-{index}", 0.9, f"{tag_type} evidence"))

    result = finalize_event_tags(tags, max_tags=100)
    counts = {
        tag_type: sum(tag.tag_type == tag_type for tag in result)
        for tag_type in ("style", "format", "mood", "theme", "instrumentation", "series")
    }

    assert len(result) == 12
    assert counts["style"] <= 6
    assert counts["format"] <= 3
    assert counts["mood"] <= 3
    assert counts["theme"] <= 4
    assert counts["instrumentation"] <= 5
    assert counts["series"] <= 1


def test_final_order_prefers_structured_styles_then_stable_type_priority():
    tags = finalize_event_tags(
        [
            EventTag("mood", "dark", 1.0, "dark"),
            EventTag("style", "techno", 1.0, "description: techno"),
            EventTag("style", "house", 1.0, "structured_genre: House"),
            EventTag("format", "dj-set", 1.0, "DJ set"),
        ],
        max_tags=12,
    )
    assert [(tag.tag_type, tag.tag_value) for tag in tags] == [
        ("style", "house"),
        ("style", "techno"),
        ("format", "dj-set"),
        ("mood", "dark"),
    ]


def test_structured_style_wins_over_description_duplicate():
    tags = canonical_event_style_tags(
        sources=EventSourceFields(
            description="A house music night.",
            structured_genres=("House",),
        )
    )
    assert [(tag.tag_value, tag.evidence, tag.confidence) for tag in tags] == [
        ("house", "structured_genre: House", 1.0)
    ]


def test_style_evidence_includes_context_not_only_matched_word():
    text = "The night moves through acid, new-wave and disco influences."
    tags = canonical_event_style_tags(sources=EventSourceFields(description=text))
    acid = next(tag for tag in tags if tag.tag_value == "acid")
    assert acid.evidence.startswith("description:")
    assert "acid" in acid.evidence
    assert acid.evidence != "description: acid"
    assert "new-wave and disco influences" in acid.evidence


def test_zero_tag_validation_does_not_invent_fallback_tags():
    tags = merge_event_styles_and_metadata(
        "Marketing prose with no controlled reusable event metadata.",
        parse_event_tags_response(
            {
                "tags": [
                    {
                        "type": "format",
                        "value": "party",
                        "confidence": 1.0,
                        "evidence": "Marketing prose",
                    }
                ]
            },
            max_tags=12,
            event_text="Marketing prose with no controlled reusable event metadata.",
        ),
        max_tags=12,
    )
    assert tags == []


def test_high_energy_is_deterministic_mood_not_hi_nrg_style():
    tags = merge_event_styles_and_metadata(
        "",
        [],
        max_tags=12,
        sources=EventSourceFields(description="A high-energy set."),
    )
    assert [(tag.tag_type, tag.tag_value) for tag in tags] == [("mood", "energetic")]


@pytest.mark.parametrize(
    "text",
    [
        "Live Show 21:30Uhr",
        "live set by Artist",
        "live act",
        "live PA",
        "hardware live",
        "Artist performing live",
        "Artist (live)",
        "Artist — live",
        "Artist - live",
    ],
)
def test_deterministic_live_format_recovers_explicit_performance(text):
    tags = merge_event_styles_and_metadata(
        "",
        [],
        max_tags=12,
        sources=EventSourceFields(title=text),
    )
    assert ("format", "live") in [(tag.tag_type, tag.tag_value) for tag in tags]


@pytest.mark.parametrize("text", ["live visuals", "live stream", "live broadcast", "live airing"])
def test_deterministic_live_format_keeps_negative_contexts_rejected(text):
    tags = merge_event_styles_and_metadata(
        "",
        [],
        max_tags=12,
        sources=EventSourceFields(description=text),
    )
    assert ("format", "live") not in [(tag.tag_type, tag.tag_value) for tag in tags]


@pytest.mark.parametrize(
    ("title", "description", "expected"),
    [
        (
            "Push Play Kinky Party",
            "A safer space. Consent is non-negotiable.",
            {"kink", "safer-space", "consent"},
        ),
        ("Open Decks for FLINTA", "", {"flinta"}),
        ("Charity Event", "all proceeds go directly to Tierheim Berlin", {"fundraiser"}),
        ("Thirsty queer thursday", "", {"queer"}),
        ("OVERLOAD", "OVERLOAD is queer play-aware, anti-racist", {"queer", "anti-racist"}),
        (
            "Brazilian night",
            "all-Brazilian, FLINTA* lineup. safe and inclusive dancefloor",
            {"flinta", "safer-space", "inclusive"},
        ),
    ],
)
def test_deterministic_event_themes_recover_explicit_event_phrases(title, description, expected):
    tags = merge_event_styles_and_metadata(
        "",
        [],
        max_tags=12,
        sources=EventSourceFields(title=title, description=description),
    )
    assert expected <= {tag.tag_value for tag in tags if tag.tag_type == "theme"}
    assert all(tag.evidence and ":" in tag.evidence for tag in tags)


@pytest.mark.parametrize(
    "description",
    [
        "co-founder of a BIPOC collective",
        "runs a FLINTA agency",
        "curates inclusive events",
        "member of a queer organization",
    ],
)
def test_deterministic_event_themes_reject_biography_only_context(description):
    tags = merge_event_styles_and_metadata(
        "",
        [],
        max_tags=12,
        sources=EventSourceFields(description=description),
    )
    assert [tag for tag in tags if tag.tag_type == "theme"] == []


def test_title_first_series_name_beats_description_acronym():
    assert canonicalize_series(
        "GIS",
        title="Gather in Sound Vol. 4",
        evidence="GIS Vol. 4",
    ) == ["gather in sound"]


def test_series_title_normalization_handles_real_title_variants_conservatively():
    push_play = merge_event_styles_and_metadata(
        "",
        [],
        max_tags=12,
        sources=EventSourceFields(title="Push Play Kinky Party//Peach Edition"),
    )
    season_opening = merge_event_styles_and_metadata(
        "",
        [],
        max_tags=12,
        sources=EventSourceFields(title="Crêpes & Open Decks - Season Opening 2026"),
    )
    assert [(tag.tag_type, tag.tag_value) for tag in push_play if tag.tag_type == "series"] == [
        ("series", "push play")
    ]
    assert [tag for tag in season_opening if tag.tag_type == "series"] == []


def test_repeated_title_series_roots_remove_artist_and_host_suffixes():
    roots = repeated_series_title_roots(
        [
            "electronic.thursday mit Semodi",
            "electronic.thursday mit Another Artist",
            "Tresor New Faces hosted by Jelena",
            "Tresor New Faces hosted by Someone Else",
            "One-off title",
        ]
    )
    assert roots == {"electronic.thursday", "tresor new faces"}


@pytest.mark.parametrize(
    ("first_title", "second_title", "expected"),
    [
        ("[EASTER WEEKEND] DECOY with Artist", "DECOY with Another Artist", "decoy"),
        ("KOLLEGIAL pres. by BSTHP - with Artist", "KOLLEGIAL pres. by Other Host", "kollegial"),
        ("Who got da Props? (Open Mic with DJ BOOM BAP)", "Who got da Props? (Open Mic with DJ TWO)", "who got da props?"),
        ("bratty • with charli xcx", "bratty • with another artist", "bratty"),
    ],
)
def test_repeated_title_roots_remove_non_series_title_noise(first_title, second_title, expected):
    assert expected in repeated_series_title_roots([first_title, second_title])


def test_identical_repeated_one_off_title_is_not_enough_for_series():
    assert repeated_series_title_roots(["Soda sucht Sprudel", "Soda sucht Sprudel"]) == set()


def test_repeated_title_root_adds_deterministic_series_with_title_evidence():
    tags = merge_event_styles_and_metadata(
        "",
        [],
        max_tags=12,
        sources=EventSourceFields(
            title="Tresor New Faces hosted by Jelena",
            repeated_title_root="tresor new faces",
        ),
    )
    series = [tag for tag in tags if tag.tag_type == "series"]
    assert [(tag.tag_value, tag.evidence) for tag in series] == [
        ("tresor new faces", "title: Tresor New Faces hosted by Jelena")
    ]


def test_configured_global_limit_can_be_lower_than_twelve(monkeypatch):
    monkeypatch.setenv("EVENT_TAG_EXTRACTION_MAX_TAGS", "4")
    monkeypatch.setenv("OPENAI_EXTRACTION_MODEL", "test")
    assert EventTagExtractionConfig.from_env().max_tags == 4


def test_single_and_batch_event_prompts_share_strict_rules():
    single = event_user_prompt("Night", "Text", 10)
    batch = event_batch_user_prompt([{"id": 1, "name": "Night", "text": "Text"}], 10)

    for prompt in (single, batch):
        assert "Do not extract musical styles or genres" in prompt
        assert "Every tag must include a short non-empty evidence phrase" in prompt
        assert "ticket, price, venue amenity, dress-code, date, access" in prompt
        assert "explicit recurrence/franchise evidence" in prompt
        assert '"type": "format|mood|theme|instrumentation|series"' in prompt


def test_openai_and_batch_paths_apply_identical_canonicalization(monkeypatch):
    payload = json.dumps(
        {
            "tags": [
                {"type": "format", "value": "live act", "confidence": 0.9, "evidence": "live act"}
            ]
        }
    )
    monkeypatch.setattr(extraction, "create_chat_completion", lambda *args, **kwargs: payload)
    config = EventTagExtractionConfig(model="test")

    single = extract_event_tags_with_llm(
        None,
        event_name="Night",
        event_text="A live act.",
        config=config,
    )
    batch_payload = json.dumps(
        {
            "events": [
                {
                    "eventId": 1,
                    "tags": [
                        {
                            "type": "format",
                            "value": "live act",
                            "confidence": 0.9,
                            "evidence": "live act",
                        }
                    ],
                }
            ]
        }
    )
    monkeypatch.setattr(extraction, "create_chat_completion", lambda *args, **kwargs: batch_payload)
    batch = extract_event_tag_batch_with_llm(
        None,
        events=[{"id": 1, "name": "Night", "text": "A live act."}],
        config=config,
    )

    assert [(tag.tag_type, tag.tag_value) for tag in single] == [("format", "live")]
    assert [(tag.tag_type, tag.tag_value) for tag in batch[1]] == [("format", "live")]


def test_azure_path_uses_event_rules_and_canonicalization(monkeypatch):
    calls = {}

    def fake_completion(**kwargs):
        calls.update(kwargs)
        return json.dumps(
            {
                "tags": [
                    {
                        "type": "theme",
                        "value": "safe space",
                        "confidence": 0.9,
                        "evidence": "safe space",
                    }
                ]
            }
        )

    monkeypatch.setattr(extraction, "create_azure_responses_completion", fake_completion)
    tags = extract_event_tags_with_llm(
        None,
        event_name="Night",
        event_text="A safe space.",
        config=EventTagExtractionConfig(
            provider="azure",
            api="responses",
            model="test",
            azure_responses_url="https://example.test",
        ),
    )

    assert [(tag.tag_type, tag.tag_value) for tag in tags] == [("theme", "safer-space")]
    assert "Do not extract musical styles or genres" in calls["instructions"]


def test_chunk_fallback_uses_same_final_merge(monkeypatch):
    monkeypatch.setattr(extraction, "split_biography_chunks", lambda *_args, **_kwargs: ["one", "two"])
    monkeypatch.setattr(
        extraction,
        "extract_event_tags_with_llm",
        lambda *_args, **_kwargs: [EventTag("format", "live", 0.9, "live set")],
    )
    result = extract_event_tags_with_chunked_fallback(
        None,
        event_name="Night",
        event_text="one two",
        config=EventTagExtractionConfig(model="test"),
    )
    assert result.processed_chunks == 2
    assert [(tag.tag_type, tag.tag_value) for tag in result.tags] == [("format", "live")]


def test_jsonl_record_and_completion_streams_are_separate(capsys):
    config = EventTagExtractionConfig(model="test")
    line = event_tags_json_line(
        {"id": 1, "name": "Night"},
        [EventTag("format", "dj-set", 1.0, "DJ set")],
        config,
    )
    print(line)
    print_completion_summary(config, processed=1, skipped=0, failed=0)

    captured = capsys.readouterr()
    assert json.loads(captured.out)["eventId"] == 1
    assert "Event tag extraction complete" not in captured.out
    assert "Event tag extraction complete" in captured.err


def test_dry_run_output_does_not_write_or_commit():
    class NoWriteConnection:
        def commit(self):
            raise AssertionError("dry-run must not commit")

    output = StringIO()
    output_or_persist_event_tags(
        NoWriteConnection(),
        event={"id": 1, "name": "Night"},
        tags=[EventTag("format", "dj-set", 1.0, "DJ set")],
        config=EventTagExtractionConfig(model="test"),
        dry_run=True,
        output=output,
    )
    assert json.loads(output.getvalue())["eventId"] == 1


def test_event_selection_uses_deterministic_id_order_and_offset():
    class FakeCursor:
        def __init__(self):
            self.calls = []
            self.rows = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, sql, params=None):
            params = list(params or [])
            self.calls.append((sql, params))
            if "SELECT\n            e.id" in sql:
                offset = params[-1] if " OFFSET %s" in sql else 0
                self.rows = [
                    {
                        "id": offset + index + 1,
                        "title": f"Event {offset + index + 1}",
                        "name": f"Event {offset + index + 1}",
                    }
                    for index in range(100)
                ]
            elif "SELECT title FROM events" in sql:
                self.rows = [{"title": "Event 1"}, {"title": "Event 2"}]
            else:
                self.rows = []

        def fetchall(self):
            return self.rows

    class FakeConnection:
        def __init__(self):
            self.fake_cursor = FakeCursor()

        def cursor(self):
            return self.fake_cursor

    first_connection = FakeConnection()
    second_connection = FakeConnection()
    first = fetch_event_texts(first_connection, limit=100, offset=0)
    second = fetch_event_texts(second_connection, limit=100, offset=100)

    assert {event["id"] for event in first}.isdisjoint(event["id"] for event in second)
    selection_sql, selection_params = second_connection.fake_cursor.calls[0]
    assert "ORDER BY e.id ASC" in selection_sql
    assert "LIMIT %s OFFSET %s" in selection_sql
    assert selection_params == [100, 100]
