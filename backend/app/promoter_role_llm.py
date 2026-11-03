"""Validate model-proposed roles before they can enter the derived data layer."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from typing import Literal

from app.artist_tag_extraction import create_chat_completion
from app.event_tag_extraction import EventTagExtractionConfig, create_extraction_client
from app.promoter_roles import DESCRIPTION_LIMIT, EventRoleInput, normalize_name

Role = Literal["organizer", "venue", "both", "unknown"]


class InvalidRoleResponse(ValueError):
    """A response failed structural or evidence validation."""

    input_tokens: int | None = None
    output_tokens: int | None = None


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
    input_tokens: int | None = None
    output_tokens: int | None = None


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
        "and evidence as a short exact substring of the input. Candidates may contain "
        "organizers missing from the listed RA promoters, only when there is explicit textual "
        "evidence; each candidate has name, confidence and exact evidence of organizing. "
        "When uncertain use unknown. Never invent IDs or quotations."
    )
    usage: list[tuple[int | None, int | None]] = []
    for attempt in range(2):
        retry_hint = "" if attempt == 0 else "\nReturn a valid JSON object with every listed ID and exact, non-empty evidence copied from the input."
        response = create_chat_completion(client, prompt=prompt + retry_hint, config=config, instructions=instructions,
                                          usage_callback=lambda incoming, outgoing: usage.append((incoming, outgoing)))
        try:
            result = parse_role_response(response, event)
            incoming = sum(item[0] for item in usage if item[0] is not None) if len(usage) == attempt + 1 and all(item[0] is not None for item in usage) else None
            outgoing = sum(item[1] for item in usage if item[1] is not None) if len(usage) == attempt + 1 and all(item[1] is not None for item in usage) else None
            return replace(result, input_tokens=incoming, output_tokens=outgoing)
        except InvalidRoleResponse as error:
            if attempt == 1:
                if len(usage) == 2 and all(item[0] is not None for item in usage):
                    error.input_tokens = sum(item[0] for item in usage if item[0] is not None)
                if len(usage) == 2 and all(item[1] is not None for item in usage):
                    error.output_tokens = sum(item[1] for item in usage if item[1] is not None)
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
        confidence = _confidence(item.get("confidence"))
        evidence = _evidence(item.get("evidence"), sources)
        if role == "both":
            name = next(profile.name for profile in event.promoters if profile.id == promoter_id)
            # A location mention alone does not prove that the venue co-organized.
            credit = re.compile(r"(?<!\w)" + re.escape(name) +
                                r"\s+(?:presents?|invites?|hosts?|organizes?|organises?|curates?)\b", re.IGNORECASE)
            if not credit.search(evidence):
                role = "unknown"
        roles.append(ProposedRole(promoter_id, role, confidence, evidence))
    if seen != ids:
        raise InvalidRoleResponse("missing promoter role")
    candidates: list[OrganizerCandidate] = []
    existing_names = {normalize_name(profile.name) for profile in event.promoters}
    for item in payload.get("candidates", []):
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise InvalidRoleResponse("invalid candidate")
        name = item["name"].strip()
        evidence = _evidence(item.get("evidence"), sources[:2])
        if not name or not normalize_name(name) or len(name) > 200 or name.casefold() not in evidence.casefold():
            raise InvalidRoleResponse("candidate name not supported by evidence")
        if normalize_name(name) in existing_names:
            raise InvalidRoleResponse("candidate duplicates an existing RA profile")
        candidates.append(OrganizerCandidate(name, _confidence(item.get("confidence")), evidence))
    return RoleResponse(tuple(roles), tuple(candidates))
