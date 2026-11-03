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
