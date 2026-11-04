import json

import pytest

from app.promoter_role_llm import InvalidRoleResponse, classify_with_llm, parse_role_response
from app.promoter_roles import EventRoleInput, PromoterProfile


EVENT = EventRoleInput(1, "Romantic Fiction & 8MM present Lila", "", 1, "8MM", (PromoterProfile(4, "8MM"),))


def test_valid_role_evidence_is_retained():
    raw = json.dumps({"roles": [{"promoter_id": 4, "role": "both", "confidence": 0.9, "evidence": "8MM present"}]})
    result = parse_role_response(raw, EVENT)
    assert result.roles[0].role == "both"
    assert result.roles[0].evidence == "8MM present"


@pytest.mark.parametrize("item", [
    {"promoter_id": 5, "role": "both", "confidence": 0.9, "evidence": "8MM present"},
    {"promoter_id": 4, "role": "both", "confidence": 0.9, "evidence": "fabricated"},
    {"promoter_id": 4, "role": "both", "confidence": 1.5, "evidence": "8MM present"},
])
def test_invalid_model_decisions_are_rejected(item):
    with pytest.raises(InvalidRoleResponse):
        parse_role_response(json.dumps({"roles": [item]}), EVENT)


def test_missing_roles_and_invalid_json_are_rejected():
    for raw in ('not json', '{"roles": []}'):
        with pytest.raises(InvalidRoleResponse):
            parse_role_response(raw, EVENT)


def test_text_only_candidate_requires_quote_containing_its_name():
    event = EventRoleInput(2, "Collective Alpha presents a concert", "", None, None, ())
    raw = json.dumps({"roles": [], "candidates": [{"name": "Collective Alpha", "confidence": 0.8, "evidence": "Collective Alpha presents"}]})
    assert parse_role_response(raw, event).candidates[0].name == "Collective Alpha"


def test_candidate_can_supplement_ra_promoters_when_text_explicitly_credits_it():
    event = EventRoleInput(3, "Collective x Club present a night", "", 1, "Club", (PromoterProfile(4, "Collective"),))
    raw = json.dumps({"roles": [{"promoter_id": 4, "role": "organizer", "confidence": 0.9, "evidence": "Collective x Club present"}],
                      "candidates": [{"name": "Club", "confidence": 0.9, "evidence": "Collective x Club present"}]})
    assert parse_role_response(raw, event).candidates[0].name == "Club"


def test_candidate_cannot_duplicate_existing_ra_profile():
    raw = json.dumps({"roles": [{"promoter_id": 4, "role": "both", "confidence": 1, "evidence": "8MM present"}],
                      "candidates": [{"name": "8MM", "confidence": 1, "evidence": "8MM present"}]})
    with pytest.raises(InvalidRoleResponse, match="duplicates"):
        parse_role_response(raw, EVENT)


def test_punctuation_only_candidate_is_rejected():
    event = EventRoleInput(1, "!!! presents", "", None, None, ())
    raw = json.dumps({"roles": [], "candidates": [{"name": "!!!", "confidence": 1, "evidence": "!!! presents"}]})
    with pytest.raises(InvalidRoleResponse):
        parse_role_response(raw, event)


def test_model_path_uses_ingestion_configuration_and_validates_response(monkeypatch):
    from app import promoter_role_llm

    config = object()
    monkeypatch.setattr(promoter_role_llm.EventTagExtractionConfig, "from_env", lambda: config)
    monkeypatch.setattr(promoter_role_llm, "create_extraction_client", lambda received: received)
    monkeypatch.setattr(promoter_role_llm, "create_chat_completion", lambda client, **kwargs: json.dumps({"roles": [{"promoter_id": 4, "role": "both", "confidence": 1, "evidence": "8MM present"}]}))
    assert classify_with_llm(EVENT).roles[0].role == "both"


def test_invalid_model_json_retries_once_then_accepts_valid_response(monkeypatch):
    from app import promoter_role_llm

    outputs = iter(['invalid', json.dumps({"roles": [{"promoter_id": 4, "role": "both", "confidence": 1, "evidence": "8MM present"}]})])
    monkeypatch.setattr(promoter_role_llm.EventTagExtractionConfig, "from_env", lambda: object())
    monkeypatch.setattr(promoter_role_llm, "create_extraction_client", lambda received: received)
    monkeypatch.setattr(promoter_role_llm, "create_chat_completion", lambda client, **kwargs: next(outputs))
    assert classify_with_llm(EVENT).roles[0].role == "both"


def test_invalid_model_json_has_bounded_retry(monkeypatch):
    from app import promoter_role_llm

    calls = []
    monkeypatch.setattr(promoter_role_llm.EventTagExtractionConfig, "from_env", lambda: object())
    monkeypatch.setattr(promoter_role_llm, "create_extraction_client", lambda received: received)
    monkeypatch.setattr(promoter_role_llm, "create_chat_completion", lambda client, **kwargs: calls.append(1) or "invalid")
    with pytest.raises(InvalidRoleResponse):
        classify_with_llm(EVENT)
    assert len(calls) == 2


def test_usage_includes_invalid_response_retry(monkeypatch):
    from app import promoter_role_llm

    outputs = iter(['invalid', json.dumps({"roles": [{"promoter_id": 4, "role": "both", "confidence": 1, "evidence": "8MM present"}]})])
    monkeypatch.setattr(promoter_role_llm.EventTagExtractionConfig, "from_env", lambda: object())
    monkeypatch.setattr(promoter_role_llm, "create_extraction_client", lambda received: received)

    def complete(client, **kwargs):
        kwargs["usage_callback"](10, 5)
        return next(outputs)

    monkeypatch.setattr(promoter_role_llm, "create_chat_completion", complete)
    result = classify_with_llm(EVENT)
    assert (result.input_tokens, result.output_tokens) == (20, 10)


def test_usage_is_retained_when_both_responses_fail_validation(monkeypatch):
    from app import promoter_role_llm

    monkeypatch.setattr(promoter_role_llm.EventTagExtractionConfig, "from_env", lambda: object())
    monkeypatch.setattr(promoter_role_llm, "create_extraction_client", lambda received: received)

    def complete(client, **kwargs):
        kwargs["usage_callback"](10, 5)
        return "invalid"

    monkeypatch.setattr(promoter_role_llm, "create_chat_completion", complete)
    with pytest.raises(InvalidRoleResponse) as error:
        classify_with_llm(EVENT)
    assert (error.value.input_tokens, error.value.output_tokens) == (20, 10)


def test_retry_explains_safe_validation_reason(monkeypatch):
    from app import promoter_role_llm

    prompts = []
    outputs = iter([json.dumps({"roles": [{"promoter_id": 4, "role": "both", "confidence": 1,
                                          "evidence": "made-up text"}]}),
                    json.dumps({"roles": [{"promoter_id": 4, "role": "both", "confidence": 1,
                                          "evidence": "8MM present"}]})])
    monkeypatch.setattr(promoter_role_llm.EventTagExtractionConfig, "from_env", lambda: object())
    monkeypatch.setattr(promoter_role_llm, "create_extraction_client", lambda received: received)

    def complete(client, **kwargs):
        prompts.append(kwargs["prompt"])
        return next(outputs)

    monkeypatch.setattr(promoter_role_llm, "create_chat_completion", complete)
    assert classify_with_llm(EVENT).roles[0].role == "both"
    assert "previous evidence was not an exact input substring" in prompts[1]
    assert "made-up text" not in prompts[1]


def test_retry_can_omit_candidate_without_supported_name(monkeypatch):
    from app import promoter_role_llm

    role = {"promoter_id": 4, "role": "both", "confidence": 1, "evidence": "8MM present"}
    invalid = {"roles": [role], "candidates": [{"name": "Other", "confidence": 1, "evidence": "8MM present"}]}
    outputs = iter([json.dumps(invalid), json.dumps({"roles": [role], "candidates": []})])
    prompts = []
    monkeypatch.setattr(promoter_role_llm.EventTagExtractionConfig, "from_env", lambda: object())
    monkeypatch.setattr(promoter_role_llm, "create_extraction_client", lambda config: config)

    def complete(client, **kwargs):
        prompts.append(kwargs["prompt"])
        return next(outputs)

    monkeypatch.setattr(promoter_role_llm, "create_chat_completion", complete)
    assert classify_with_llm(EVENT).candidates == ()
    assert "Omit any candidate" in prompts[1]


def test_bad_role_evidence_after_retry_becomes_unknown(monkeypatch):
    from app import promoter_role_llm

    raw = json.dumps({"roles": [{"promoter_id": 4, "role": "both", "confidence": 1,
                                 "evidence": "made-up text"}]})
    monkeypatch.setattr(promoter_role_llm.EventTagExtractionConfig, "from_env", lambda: object())
    monkeypatch.setattr(promoter_role_llm, "create_extraction_client", lambda received: received)
    monkeypatch.setattr(promoter_role_llm, "create_chat_completion", lambda *args, **kwargs: raw)
    role = classify_with_llm(EVENT).roles[0]
    assert (role.role, role.confidence, role.evidence) == ("unknown", 0.0, "8MM")


def test_venue_mention_does_not_prove_it_coorganized():
    event = EventRoleInput(2, "OMANA at Funkhaus Berlin", "OMANA transform Funkhaus Berlin", 1,
                           "Funkhaus Berlin", (PromoterProfile(4, "Funkhaus Berlin"),))
    raw = json.dumps({"roles": [{"promoter_id": 4, "role": "both", "confidence": 0.98,
                                 "evidence": "OMANA transform Funkhaus Berlin"}]})
    assert parse_role_response(raw, event).roles[0].role == "unknown"


def test_explicit_invitation_can_support_venue_coorganizer():
    event = EventRoleInput(2, "Heaven and Studio 1111 invite", "", 1, "Studio 1111",
                           (PromoterProfile(4, "Studio 1111"),))
    raw = json.dumps({"roles": [{"promoter_id": 4, "role": "both", "confidence": 0.88,
                                 "evidence": "Heaven and Studio 1111 invite"}]})
    assert parse_role_response(raw, event).roles[0].role == "both"


def test_venue_cannot_become_organizer_based_only_on_its_name():
    event = EventRoleInput(2, "OMANA at Funkhaus Berlin", "", 1,
                           "Funkhaus Berlin", (PromoterProfile(4, "Funkhaus Berlin"),))
    raw = json.dumps({"roles": [{"promoter_id": 4, "role": "organizer", "confidence": 0.98,
                                 "evidence": "Funkhaus Berlin"}]})
    assert parse_role_response(raw, event).roles[0].role == "unknown"


def test_venue_with_club_suffix_needs_organizer_evidence():
    event = EventRoleInput(2, "A night at Renate", "", 1, "Renate", (PromoterProfile(4, "Renate Club"),))
    raw = json.dumps({"roles": [{"promoter_id": 4, "role": "organizer", "confidence": 0.98,
                                 "evidence": "Renate Club"}]})
    assert parse_role_response(raw, event).roles[0].role == "unknown"


def test_venue_with_club_suffix_keeps_explicit_organizer_credit():
    event = EventRoleInput(2, "Renate Club presents", "", 1, "Renate", (PromoterProfile(4, "Renate Club"),))
    raw = json.dumps({"roles": [{"promoter_id": 4, "role": "both", "confidence": 0.9,
                                 "evidence": "Renate Club presents"}]})
    assert parse_role_response(raw, event).roles[0].role == "both"


def test_venue_organizer_credit_with_hosted_by_is_retained():
    event = EventRoleInput(2, "Summer afternoon", "hosted by OYE Records", 1, "OYE Records",
                           (PromoterProfile(4, "OYE Records"),))
    raw = json.dumps({"roles": [{"promoter_id": 4, "role": "both", "confidence": 0.9,
                                 "evidence": "hosted by OYE Records"}]})
    assert parse_role_response(raw, event).roles[0].role == "both"


def test_venue_presenter_with_appositive_is_retained():
    text = "90mil, a temporary DIY space in Berlin, presents their farewell festival"
    event = EventRoleInput(2, "A 90mil Festival", text, 1, "90mil", (PromoterProfile(4, "90mil"),))
    raw = json.dumps({"roles": [{"promoter_id": 4, "role": "both", "confidence": 0.9, "evidence": text}]})
    assert parse_role_response(raw, event).roles[0].role == "both"


def test_venue_mention_with_appositive_is_not_a_presenter_credit():
    text = "90mil, a temporary DIY space in Berlin, welcomes festival guests"
    event = EventRoleInput(2, "A festival", text, 1, "90mil", (PromoterProfile(4, "90mil"),))
    raw = json.dumps({"roles": [{"promoter_id": 4, "role": "both", "confidence": 0.9, "evidence": text}]})
    assert parse_role_response(raw, event).roles[0].role == "unknown"


def test_organizer_must_be_named_in_event_evidence():
    event = EventRoleInput(2, "Klubnacht", "playing here for the second time", 1,
                           "Berghain | Panorama Bar | Säule", (PromoterProfile(4, "OstGut GmbH"),))
    raw = json.dumps({"roles": [{"promoter_id": 4, "role": "organizer", "confidence": 0.9,
                                 "evidence": "playing here for the second time"}]})
    assert parse_role_response(raw, event).roles[0].role == "unknown"


def test_profile_name_alone_is_not_event_organizer_evidence():
    event = EventRoleInput(2, "A gathering", "Doors open at 10", 1,
                           "Somewhere", (PromoterProfile(4, "Collective"),))
    raw = json.dumps({"roles": [{"promoter_id": 4, "role": "organizer", "confidence": 0.9,
                                 "evidence": "Collective"}]})
    assert parse_role_response(raw, event).roles[0].role == "unknown"


def test_venue_overlap_does_not_become_organizer_from_profile_name():
    event = EventRoleInput(2, "Birgits WEEKENDER", "Tickets at the door", 1,
                           "Birgit", (PromoterProfile(4, "Birgit & Bier"),))
    raw = json.dumps({"roles": [{"promoter_id": 4, "role": "organizer", "confidence": 0.9,
                                 "evidence": "Birgit & Bier"}]})
    assert parse_role_response(raw, event).roles[0].role == "unknown"


def test_venue_alias_can_be_credited_by_venue_name():
    event = EventRoleInput(2, "Release party", "Eclectic Limited & Giri present", 1,
                           "Giri", (PromoterProfile(4, "giriberlino"),))
    raw = json.dumps({"roles": [{"promoter_id": 4, "role": "both", "confidence": 0.9,
                                 "evidence": "Eclectic Limited & Giri present"}]})
    assert parse_role_response(raw, event).roles[0].role == "both"


def test_venue_events_profile_requires_explicit_organizer_credit():
    event = EventRoleInput(2, "OXI Groove Affair", "The party returns to OXI.", 1,
                           "OXI", (PromoterProfile(4, "OXI Events"),))
    raw = json.dumps({"roles": [{"promoter_id": 4, "role": "organizer", "confidence": 0.9,
                                 "evidence": "OXI Groove Affair"}]})
    assert parse_role_response(raw, event).roles[0].role == "unknown"


def test_venue_presenter_abbreviation_is_a_credit():
    event = EventRoleInput(2, "M.A.R.A.", "OST pres. M.A.R.A.", 1,
                           "OST", (PromoterProfile(4, "OST"),))
    raw = json.dumps({"roles": [{"promoter_id": 4, "role": "both", "confidence": 0.9,
                                 "evidence": "OST pres. M.A.R.A."}]})
    assert parse_role_response(raw, event).roles[0].role == "both"


def test_different_name_containing_club_is_not_automatically_venue():
    event = EventRoleInput(2, "Clubnight presents", "", 1, "Night", (PromoterProfile(4, "Clubnight"),))
    raw = json.dumps({"roles": [{"promoter_id": 4, "role": "organizer", "confidence": 0.9,
                                 "evidence": "Clubnight presents"}]})
    assert parse_role_response(raw, event).roles[0].role == "organizer"
