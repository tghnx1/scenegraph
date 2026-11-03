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
