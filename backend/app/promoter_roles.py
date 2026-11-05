"""Conservative deterministic signals for event promoter role review."""

from __future__ import annotations

import re
import unicodedata
import hashlib
import json
from dataclasses import dataclass
from typing import Literal, TypedDict


CLASSIFIER_VERSION = "promoter-role-v13"
NORMALIZATION_VERSION = "unicode-nfkc-alnum-v1"
DESCRIPTION_LIMIT = 12000


@dataclass(frozen=True, slots=True)
class PromoterProfile:
    id: int
    name: str
    # Only confirmed identity memberships may be included here.
    identity_id: int | None = None


@dataclass(frozen=True, slots=True)
class EventRoleInput:
    event_id: int
    title: str
    description: str | None
    venue_id: int | None
    venue_name: str | None
    promoters: tuple[PromoterProfile, ...]


class ProfileSnapshot(TypedDict):
    id: int
    name_hash: str
    identity_id: int | None


class EventSnapshot(TypedDict):
    event_id: int
    title_hash: str
    description_hash: str
    venue_id: int | None
    venue_name_hash: str | None
    promoters: list[ProfileSnapshot]


def role_input_snapshot(event: EventRoleInput) -> EventSnapshot:
    """Structured counterpart of the SQL eligibility view's input comparison."""
    def digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    return {
        "event_id": event.event_id,
        "title_hash": digest(event.title),
        "description_hash": digest((event.description or "")[:DESCRIPTION_LIMIT]),
        "venue_id": event.venue_id,
        "venue_name_hash": digest(event.venue_name) if event.venue_name is not None else None,
        "promoters": [
            {"id": p.id, "name_hash": digest(p.name), "identity_id": p.identity_id}
            for p in sorted(event.promoters, key=lambda p: p.id)
        ],
    }


def role_input_hash(event: EventRoleInput, *, version: str = CLASSIFIER_VERSION) -> str:
    """Identify all input that affects a classification, independent of query order."""
    payload = {
        "event_id": event.event_id,
        "title": event.title,
        "description": (event.description or "")[:DESCRIPTION_LIMIT],
        "venue_id": event.venue_id,
        "venue_name": event.venue_name,
        "promoters": [
            {"id": p.id, "name": p.name, "identity_id": p.identity_id}
            for p in sorted(event.promoters, key=lambda p: p.id)
        ],
        "classifier_version": version,
        "normalization_version": NORMALIZATION_VERSION,
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def independent_profile_count(profiles: tuple[PromoterProfile, ...]) -> int:
    """Count only confirmed aliases together; unconfirmed profiles remain distinct."""
    return len({("identity", p.identity_id) if p.identity_id is not None else ("profile", p.id) for p in profiles})


@dataclass(frozen=True, slots=True)
class RoleSignal:
    role: Literal["organizer", "both", "unknown"]
    evidence: str | None
    venue_name_match: bool


def normalize_name(value: str) -> str:
    """Normalize names for exact comparison without erasing non-Latin letters."""
    return "".join(c for c in unicodedata.normalize("NFKC", value).casefold() if c.isalnum())


def venue_name_matches(profile: str, venue: str | None) -> bool:
    """Match exact names and a separate Club prefix or suffix conservatively."""
    if not venue:
        return False

    def variants(value: str) -> set[str]:
        words = re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", value).casefold())
        result = {normalize_name(value)}
        if len(words) > 1 and words[0] == "club":
            result.add("".join(words[1:]))
        if len(words) > 1 and words[-1] == "club":
            result.add("".join(words[:-1]))
        return result - {""}

    return bool(variants(profile) & variants(venue))


def venue_name_may_match(profile: str, venue: str | None) -> bool:
    """Identify limited name overlaps that require stronger organizer evidence.

    This is not an identity merge: ambiguous overlaps remain separate profiles.
    """
    if venue_name_matches(profile, venue):
        return True
    if not venue:
        return False
    profile_key = normalize_name(profile)
    for part in re.split(r"\s+/\s+", venue):
        key = normalize_name(part)
        if len(key) < 3 or not profile_key.startswith(key):
            continue
        suffix = profile_key[len(key):]
        if suffix == "events" or (len(key) >= 4 and suffix in {"berlin", "berlino", "bier"}):
            return True
    return False


def classify_explicit_presenter(promoter: str, venue: str | None, title: str) -> RoleSignal:
    """Recognize a named presenter; leave ambiguous credits unresolved."""
    name = promoter.strip()
    normalized = normalize_name(name)
    venue_match = venue_name_matches(name, venue)
    if not name or not normalized:
        return RoleSignal("unknown", None, venue_match)
    # Require the exact name immediately before the presentation verb. This is a
    # signal, not fuzzy identity matching or a general interpretation of prose.
    pattern = re.compile(r"(?<!\w)" + re.escape(name) + r"\s+presents?\b", re.IGNORECASE)
    match = pattern.search(title)
    if match:
        return RoleSignal("both" if venue_match else "organizer", match.group(0), venue_match)
    return RoleSignal("unknown", None, venue_match)
