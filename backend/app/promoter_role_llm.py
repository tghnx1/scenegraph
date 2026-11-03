"""Validate model-proposed roles before they can enter the derived data layer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from app.artist_tag_extraction import create_chat_completion
from app.event_tag_extraction import EventTagExtractionConfig, create_extraction_client
from app.promoter_roles import DESCRIPTION_LIMIT, EventRoleInput

Role = Literal["organizer", "venue", "both", "unknown"]


class InvalidRoleResponse(ValueError):
    """A response failed structural or evidence validation."""


@dataclass(frozen=True, slots=True)
class ProposedRole:
    promoter_id: int
    role: Role
    confidence: float
    evidence: str


@dataclass(frozen=True, slots=True)
class OrganizerCandidate:
    name: str
    confidence: float
    evidence: str


@dataclass(frozen=True, slots=True)
class RoleResponse:
    roles: tuple[ProposedRole, ...]
    candidates: tuple[OrganizerCandidate, ...]


def classify_with_llm(event: EventRoleInput) -> RoleResponse:
    """Use the ingestion extraction provider and validate its untrusted answer."""
    config = EventTagExtractionConfig.from_env()
    client = create_extraction_client(config)
    prompt = json.dumps({
        "title": event.title,
        "description": (event.description or "")[:DESCRIPTION_LIMIT],
        "venue": {"id": event.venue_id, "name": event.venue_name},
        "promoters": [{"id": p.id, "name": p.name, "confirmed_identity_id": p.identity_id} for p in event.promoters],
    }, ensure_ascii=False)
    instructions = (
        "Classify each listed promoter's role for this event as organizer, venue, both, or unknown. "
        "A venue can also organize an event; mere name similarity does not prove either role. "
        "Do not infer organizers from artists or event series. Return JSON object with roles "
        "containing exactly one object per input promoter: promoter_id, role, confidence (0..1), "
        "and evidence as a short exact substring of the input. For events with no listed "
        "promoters, candidates may contain name, confidence, and exact evidence of organizing. "
        "When uncertain use unknown. Never invent IDs or quotations."
    )
    for attempt in range(2):
        retry_hint = "" if attempt == 0 else "\nReturn a valid JSON object with every listed ID and exact, non-empty evidence copied from the input."
        response = create_chat_completion(client, prompt=prompt + retry_hint, config=config, instructions=instructions)
        try:
            return parse_role_response(response, event)
        except InvalidRoleResponse:
            if attempt == 1:
                raise
    raise AssertionError("unreachable")


def _confidence(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise InvalidRoleResponse("invalid confidence")
    return float(value)


def _evidence(value: object, sources: tuple[str, ...]) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 1000:
        raise InvalidRoleResponse("invalid evidence")
    if not any(value in source for source in sources):
        raise InvalidRoleResponse("evidence is not present in input")
    return value


def parse_role_response(raw: str, event: EventRoleInput) -> RoleResponse:
    """Reject unknown IDs, unsupported roles, duplicate IDs and fabricated evidence."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InvalidRoleResponse("invalid JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("roles"), list) or not isinstance(payload.get("candidates", []), list):
        raise InvalidRoleResponse("invalid response shape")
    sources = (event.title, (event.description or "")[:DESCRIPTION_LIMIT], event.venue_name or "", *(p.name for p in event.promoters))
    ids = {p.id for p in event.promoters}
    seen: set[int] = set()
    roles: list[ProposedRole] = []
    for item in payload["roles"]:
        if not isinstance(item, dict):
            raise InvalidRoleResponse("invalid role item")
        promoter_id, role = item.get("promoter_id"), item.get("role")
        if isinstance(promoter_id, bool) or not isinstance(promoter_id, int) or promoter_id not in ids or promoter_id in seen:
            raise InvalidRoleResponse("invalid promoter ID")
        if role not in ("organizer", "venue", "both", "unknown"):
            raise InvalidRoleResponse("invalid role")
        seen.add(promoter_id)
        roles.append(ProposedRole(promoter_id, role, _confidence(item.get("confidence")), _evidence(item.get("evidence"), sources)))
    if seen != ids:
        raise InvalidRoleResponse("missing promoter role")
    candidates: list[OrganizerCandidate] = []
    if ids and payload.get("candidates"):
        raise InvalidRoleResponse("text-only candidates require an event without RA promoters")
    for item in payload.get("candidates", []):
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise InvalidRoleResponse("invalid candidate")
        name = item["name"].strip()
        evidence = _evidence(item.get("evidence"), sources[:2])
        if not name or len(name) > 200 or name.casefold() not in evidence.casefold():
            raise InvalidRoleResponse("candidate name not supported by evidence")
        candidates.append(OrganizerCandidate(name, _confidence(item.get("confidence")), evidence))
    return RoleResponse(tuple(roles), tuple(candidates))
