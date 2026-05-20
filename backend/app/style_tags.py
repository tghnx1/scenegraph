from __future__ import annotations

import re
from typing import Any


STYLE_ALIASES: dict[str, tuple[str, ...]] = {
    "acid": ("acid",),
    "acid techno": ("acid techno",),
    "ambient": ("ambient",),
    "bass": ("bass", "bass music"),
    "breakbeat": ("breakbeat", "breakbeats", "breaks"),
    "dark disco": ("dark disco",),
    "deep house": ("deep house",),
    "disco": ("disco",),
    "dub": ("dub",),
    "dub techno": ("dub techno",),
    "ebm": ("ebm",),
    "electro": ("electro",),
    "experimental": ("experimental",),
    "hard techno": ("hard techno",),
    "hardgroove": ("hardgroove",),
    "house": ("house",),
    "hypnotic techno": ("hypnotic techno",),
    "idm": ("idm",),
    "indie dance": ("indie dance",),
    "industrial": ("industrial",),
    "italo": ("italo",),
    "leftfield": ("leftfield",),
    "minimal": ("minimal",),
    "new wave": ("new wave",),
    "post-punk": ("post-punk", "post punk"),
    "progressive": ("progressive",),
    "psychedelic": ("psychedelic",),
    "tech house": ("tech house",),
    "techno": ("techno",),
    "trance": ("trance",),
}


def normalize_style_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def style_alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias).replace(r"\ ", r"[\s\-]+")
    return re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", re.IGNORECASE)


STYLE_PATTERNS = {
    tag: tuple(style_alias_pattern(alias) for alias in aliases)
    for tag, aliases in STYLE_ALIASES.items()
}

PARENT_STYLE_TAGS: dict[str, tuple[str, ...]] = {
    "acid techno": ("acid", "techno"),
    "dark disco": ("disco",),
    "deep house": ("house",),
    "dub techno": ("dub", "techno"),
    "hard techno": ("techno",),
    "hypnotic techno": ("techno",),
    "tech house": ("house",),
}


def extract_style_tags(value: Any) -> list[str]:
    text = normalize_style_text(value).lower()
    if not text:
        return []

    tags = [
        tag
        for tag, patterns in STYLE_PATTERNS.items()
        if any(pattern.search(text) for pattern in patterns)
    ]
    tag_set = set(tags)
    for specific_tag, parent_tags in PARENT_STYLE_TAGS.items():
        if specific_tag in tag_set:
            tag_set.difference_update(parent_tags)

    return sorted(tag_set)


def style_overlap_score(source_tags: list[str], candidate_tags: list[str]) -> float:
    if not source_tags or not candidate_tags:
        return 0.0

    source_set = set(source_tags)
    candidate_set = set(candidate_tags)
    overlap = source_set & candidate_set
    union = source_set | candidate_set
    return len(overlap) / len(union)
