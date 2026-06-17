from __future__ import annotations

import re
from dataclasses import dataclass

from app.style_tags import STYLE_ALIASES, style_alias_pattern, suppress_parent_style_tags


AMBIGUOUS_STYLE_TAGS = {
    "funk",
    "house",
    "bass",
    "garage",
    "metal",
    "minimal",
    "progressive",
    "industrial",
    "classical",
    "wave",
    "country",
    "folk",
    "pop",
    "rock",
    "soul",
    "trap",
    "tribal",
    "rave",
}

AMBIGUOUS_POSITIVE_TERMS = (
    "music",
    "genre",
    "sound",
    "sounds",
    "set",
    "sets",
    "dj",
    "djs",
    "night",
    "lineup",
    "line-up",
    "party",
    "rave",
    "club",
    "beat",
    "beats",
    "rhythm",
    "rhythms",
    "record",
    "records",
    "influence",
    "influences",
    "techno",
    "house",
    "disco",
    "punk",
    "electronic",
    "musik",
    "klang",
    "klänge",
    "nacht",
    "rhythmen",
    "platten",
    "einflüsse",
)

AMBIGUOUS_NEGATIVE_CONTEXT = {
    "funk": re.compile(r"\b(?:per|via)\s+funk\b|\bfunkger[aä]t(?:e|en|s)?\b", re.IGNORECASE),
    "bass": re.compile(r"\bbass\s+(?:player|guitar|guitarist|string|strings)\b", re.IGNORECASE),
    "garage": re.compile(r"\bgarage\s+(?:door|sale|space|building)\b", re.IGNORECASE),
    "metal": re.compile(r"\bmetal\s+(?:accessor(?:y|ies)|object|objects|work|construction)\b", re.IGNORECASE),
    "progressive": re.compile(r"\bprogressive\s+(?:approach|politics|policy|thinking|movement)\b", re.IGNORECASE),
    "industrial": re.compile(r"\bindustrial\s+(?:building|space|area|architecture|design)\b", re.IGNORECASE),
    "classical": re.compile(r"\bclassical\s+(?:tradition|training|education|approach)\b", re.IGNORECASE),
    "house": re.compile(r"\bhouse\s+of\b", re.IGNORECASE),
}

STYLE_NEGATIVE_CONTEXT = re.compile(
    r"\b(?:break\s+from|not|no|without|instead\s+of|alternative\s+to|far\s+from|anything\s+but)\s+$",
    re.IGNORECASE,
)

DNB_AUDIO_BRAND_CONTEXT = re.compile(r"^\s*d&b\s+audiotechnik\b", re.IGNORECASE)


@dataclass(frozen=True)
class StyleTagMatch:
    value: str
    evidence: str
    source: str
    confidence: float


def _context_window(text: str, start: int, end: int, radius: int = 45) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)]


def extract_context_fragment(
    text: str,
    match_start: int,
    match_end: int,
    max_chars: int = 120,
) -> str:
    if not text or match_start < 0 or match_end <= match_start:
        return ""

    radius = max((max_chars - (match_end - match_start)) // 2, 0)
    start = max(0, match_start - radius)
    end = min(len(text), match_end + radius)

    if start > 0:
        next_space = re.search(r"\s", text[start:match_start])
        if next_space:
            start += next_space.end()
    if end < len(text):
        trailing = text[match_end:end]
        last_space = max(trailing.rfind(" "), trailing.rfind("\n"), trailing.rfind("\t"))
        if last_space >= 0:
            end = match_end + last_space

    fragment = re.sub(r"\s+", " ", text[start:end]).strip()
    if len(fragment) <= max_chars:
        return fragment
    shortened = fragment[:max_chars].rsplit(" ", 1)[0].strip()
    return shortened or fragment[:max_chars].strip()


def _accept_ambiguous_match(*, value: str, alias: str, source: str, text: str, start: int, end: int) -> bool:
    if source == "structured_genre":
        return True

    window = _context_window(text, start, end)
    negative = AMBIGUOUS_NEGATIVE_CONTEXT.get(value)
    if negative and negative.search(window):
        return False
    if "music" in alias or len(alias.split()) > 1:
        return True
    return _has_musical_context(text=text, start=start, end=end)


def _has_musical_context(*, text: str, start: int, end: int) -> bool:
    direct_context = "|".join(re.escape(term) for term in AMBIGUOUS_POSITIVE_TERMS)
    before = text[max(0, start - 24) : start]
    after = text[end : min(len(text), end + 24)]
    return bool(
        re.search(rf"(?:{direct_context})[\s:/-]+$", before, re.IGNORECASE)
        or re.match(rf"^[\s:/-]+(?:{direct_context})\b", after, re.IGNORECASE)
    )


def _accept_style_match(*, value: str, alias: str, source: str, text: str, start: int, end: int) -> bool:
    if source != "structured_genre":
        before = text[max(0, start - 40) : start]
        if STYLE_NEGATIVE_CONTEXT.search(before):
            return False
        if value == "drum and bass" and alias.casefold() == "d&b":
            if DNB_AUDIO_BRAND_CONTEXT.match(text[start : min(len(text), end + 40)]):
                return False
        if (
            source == "title"
            and len(alias.split()) == 1
            and text.strip().casefold() != alias.casefold()
            and not _has_musical_context(text=text, start=start, end=end)
        ):
            return False
    return value not in AMBIGUOUS_STYLE_TAGS or _accept_ambiguous_match(
        value=value,
        alias=alias,
        source=source,
        text=text,
        start=start,
        end=end,
    )


def _remove_artist_names(text: str, artist_names: tuple[str, ...]) -> str:
    cleaned = text
    for artist_name in sorted((name for name in artist_names if name), key=len, reverse=True):
        cleaned = re.sub(re.escape(artist_name), " ", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


def _matches_for_source(source: str, text: str, confidence: float) -> list[StyleTagMatch]:
    matches: dict[str, StyleTagMatch] = {}
    for canonical, aliases in STYLE_ALIASES.items():
        for alias in sorted(aliases, key=len, reverse=True):
            for match in style_alias_pattern(alias).finditer(text):
                if not _accept_style_match(
                    value=canonical,
                    alias=alias,
                    source=source,
                    text=text,
                    start=match.start(),
                    end=match.end(),
                ):
                    continue
                matches[canonical] = StyleTagMatch(
                    value=canonical,
                    evidence=(
                        match.group(0)
                        if source == "structured_genre"
                        else extract_context_fragment(text, match.start(), match.end())
                    ),
                    source=source,
                    confidence=confidence,
                )
                break
            if canonical in matches:
                break
    return list(matches.values())


def extract_event_style_matches(
    *,
    title: str = "",
    description: str = "",
    lineup_text: str = "",
    structured_genres: list[str] | tuple[str, ...] = (),
    artist_names: list[str] | tuple[str, ...] = (),
) -> list[StyleTagMatch]:
    artist_names_tuple = tuple(artist_names)
    source_values = [
        ("structured_genre", genre, 1.0) for genre in structured_genres if genre
    ] + [
        ("description", _remove_artist_names(description, artist_names_tuple), 0.95),
        ("lineup", _remove_artist_names(lineup_text, artist_names_tuple), 0.9),
        ("title", _remove_artist_names(title, artist_names_tuple), 0.85),
    ]

    selected: dict[str, StyleTagMatch] = {}
    for source, text, confidence in source_values:
        for match in _matches_for_source(source, text or "", confidence):
            selected.setdefault(match.value, match)

    retained = suppress_parent_style_tags(selected)
    return [selected[value] for value in retained]
