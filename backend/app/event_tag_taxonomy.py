from __future__ import annotations

import re
from dataclasses import dataclass

from app.event_style_tags import extract_context_fragment


EVENT_TAG_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "mood": {
        "dark": ("dark", "dark atmosphere", "dark aesthetics"),
        "raw": ("raw", "raw energy", "raw emotion"),
        "hypnotic": ("hypnotic",),
        "energetic": ("energetic", "high energy", "high-energy"),
        "euphoric": ("euphoric",),
        "intimate": ("intimate", "intimate atmosphere", "intimate evening"),
        "playful": ("playful",),
        "meditative": ("meditative",),
        "relaxed": ("relaxed",),
        "immersive": ("immersive",),
        "groovy": ("groovy",),
        "floor-focused": ("floor focused", "floor-focused", "built for the floor"),
        "experimental": ("experimental",),
        "sensual": ("sensual",),
        "atmospheric": ("atmospheric",),
    },
    "theme": {
        "community": ("community", "community driven", "community-driven"),
        "queer": ("queer", "queer friendly", "queer-friendly"),
        "flinta": (
            "flinta",
            "flinta*",
            "flinta community",
            "flinta* community",
            "flinta guests",
            "flinta lineup",
            "all-flinta lineup",
        ),
        "bipoc": ("bipoc",),
        "lgbtq": (
            "lgbtq",
            "lgbtq+",
            "lgbtqia+",
            "lgbt friendly",
            "lgbtq friendly",
            "lgbtq+ friendly",
            "lgbtqia+ friendly",
        ),
        "inclusive": ("inclusive", "inclusivity", "safe and inclusive dancefloor"),
        "safer-space": (
            "safe space",
            "safe spaces",
            "safer space",
            "safer spaces",
            "protected space",
            "protected spaces",
        ),
        "sex-positive": ("sex positive", "sex-positive", "sex-positive community"),
        "kink": ("kink", "kinky", "kink community", "kink party", "kinky party"),
        "bdsm": ("bdsm", "bdsm event", "bdsm community", "fetish party", "fetish community"),
        "consent": (
            "consent",
            "consent culture",
            "respect and consent",
            "mutual consent",
            "consent is non-negotiable",
        ),
        "anti-discrimination": (
            "anti discrimination",
            "anti-discrimination",
            "no discrimination",
            "zero tolerance discrimination",
            "discrimination-free",
        ),
        "anti-racist": ("anti racist", "anti-racist", "zero tolerance for racism"),
        "feminist": ("feminist",),
        "fundraiser": (
            "fundraiser",
            "charity event",
            "humanitarian fundraiser",
            "fundraising event",
            "all proceeds go to",
            "proceeds go directly to",
            "benefit event",
            "donation event",
        ),
        "local-scene": ("local scene", "local-scene"),
        "newcomer-support": ("newcomer support", "newcomer-support"),
    },
}

PER_TYPE_LIMITS = {
    "style": 6,
    "theme": 4,
    "mood": 3,
}

EVENT_TAG_TYPE_PRIORITY = (
    "style",
    "theme",
    "mood",
)

EVENT_TAG_REJECT_PATTERNS = {
    "mood": re.compile(
        r"\b(?:safe(?:r)? space|queer friendly|respect and consent|charity|casual music enjoyers|no dresscode vibes)\b",
        re.IGNORECASE,
    ),
}

THEME_BIOGRAPHY_CONTEXT = re.compile(
    r"\b(?:co-?founder\s+of|founder\s+of|member\s+of|runs?\s+(?:an?\s+)?agency"
    r"|founded\s+(?:an?\s+)?collective|curates?\s+inclusive\s+events|has\s+performed\s+at"
    r"|their\s+work\s+focuses\s+on|new\s+flinta\*?\s+agency)\b",
    re.IGNORECASE,
)

THEME_EVENT_LEVEL_CONTEXT = re.compile(
    r"\b(?:this|the|our)\s+(?:event|party|night|space|dancefloor)\b"
    r"|\b(?:event|party|night|space|dancefloor)\s+(?:welcomes?|is|for|dedicated|focused)\b"
    r"|\bfor\s+(?:bipoc|queer|flinta|lgbtq(?:ia)?\+?)\s+guests?\b"
    r"|\b(?:bipoc|queer|flinta|lgbtq(?:ia)?\+?)\s+guests?\s+(?:are\s+)?welcome\b"
    r"|\b(?:all[-\s]?flinta|flinta|queer|bipoc|inclusive|feminist|anti-racist|community)"
    r"(?:-focused)?[-\s]+(?:lineup|party|event|night|space)\b"
    r"|\bopen\s+decks\s+for\s+flinta\*?\b"
    r"|\bqueer\s+(?:community|play-aware|thursday)\b"
    r"|\b(?:safe|safer|protected)\s+spaces?\b"
    r"|\bsafe\s+and\s+inclusive\s+dancefloor\b"
    r"|\bsex[-\s]+positive\s+(?:party|event|space|community)\b"
    r"|\b(?:kinky|kink|fetish)\s+(?:party|event|community)\b"
    r"|\bbdsm\s+(?:party|event|community)\b"
    r"|\blgbtq(?:ia)?\+?\s+friendly\s+(?:party|event|space|night)\b"
    r"|\bconsent\s+(?:is|culture|and|policy)\b|\bmutual\s+consent\b"
    r"|\b(?:charity|benefit|donation|fundraising)\s+event\b|\bfundraiser\b"
    r"|\b(?:all\s+)?proceeds\s+go\s+(?:directly\s+)?to\b"
    r"|\bzero\s+tolerance\s+for\s+racism\b|\banti[-\s]+racist\b"
    r"|\bzero\s+tolerance\s+(?:for\s+)?discrimination\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EventTaxonomyMatch:
    tag_type: str
    value: str
    evidence: str
    source: str
    confidence: float


def normalize_event_taxonomy_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias).replace(r"\ ", r"[\s\-]+")
    return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)


EVENT_TAG_PATTERNS = {
    tag_type: {
        canonical: tuple(_alias_pattern(alias) for alias in aliases)
        for canonical, aliases in values.items()
    }
    for tag_type, values in EVENT_TAG_ALIASES.items()
}


def canonicalize_event_tag(tag_type: str, value: object) -> list[str]:
    text = normalize_event_taxonomy_text(value)
    patterns = EVENT_TAG_PATTERNS.get(tag_type)
    if not text or patterns is None:
        return []
    rejected = EVENT_TAG_REJECT_PATTERNS.get(tag_type)
    if rejected and rejected.search(text):
        return []

    values = [
        canonical
        for canonical, aliases in patterns.items()
        if any(pattern.search(text) for pattern in aliases)
    ]
    if tag_type == "mood" and "experimental" in values:
        values = [value for value in values if value != "experimental" or text == "experimental"]
    return values


def is_event_level_theme_evidence(evidence: object, event_text_context: object) -> bool:
    evidence_text = normalize_event_taxonomy_text(evidence)
    context = normalize_event_taxonomy_text(event_text_context)
    if not evidence_text or evidence_text not in context:
        return False
    if THEME_BIOGRAPHY_CONTEXT.search(evidence_text):
        return False
    return bool(THEME_EVENT_LEVEL_CONTEXT.search(evidence_text))


def evidence_supports_event_tag(
    tag_type: str,
    *,
    raw_value: object,
    canonical_value: str,
    evidence: object,
) -> bool:
    normalized_evidence = normalize_event_taxonomy_text(evidence)
    normalized_raw = normalize_event_taxonomy_text(raw_value)
    if not normalized_evidence:
        return False
    if (
        normalized_raw
        and normalized_raw in normalized_evidence
        and canonical_value in canonicalize_event_tag(tag_type, raw_value)
    ):
        return True
    return any(
        normalize_event_taxonomy_text(alias) in normalized_evidence
        for alias in EVENT_TAG_ALIASES.get(tag_type, {}).get(canonical_value, ())
    )


DETERMINISTIC_THEME_PATTERNS: dict[str, re.Pattern[str]] = {
    "safer-space": re.compile(
        r"\b(?:safe|safer|protected)\s+spaces?\b|\bsafe\s+and\s+inclusive\s+dancefloor\b",
        re.IGNORECASE,
    ),
    "flinta": re.compile(
        r"\b(?:all[-\s]?)?flinta\*?\s+(?:guests?|lineup|community)\b"
        r"|\bopen\s+decks\s+for\s+flinta\*?\b",
        re.IGNORECASE,
    ),
    "queer": re.compile(
        r"\bqueer\s+(?:party|event|night|community|play-aware|thursday)\b", re.IGNORECASE
    ),
    "fundraiser": re.compile(
        r"\b(?:charity|fundraising|benefit|donation)\s+event\b"
        r"|\bhumanitarian\s+fundraiser\b|\bfundraiser\b"
        r"|\b(?:all\s+)?proceeds\s+go\s+(?:directly\s+)?to\b",
        re.IGNORECASE,
    ),
    "anti-racist": re.compile(
        r"\banti[-\s]+racist\b|\bzero\s+tolerance\s+for\s+racism\b", re.IGNORECASE
    ),
    "sex-positive": re.compile(r"\bsex[-\s]+positive(?:\s+party)?\b", re.IGNORECASE),
    "kink": re.compile(r"\b(?:kinky|kink)\s+(?:party|community)\b", re.IGNORECASE),
    "bdsm": re.compile(
        r"\bbdsm\s+(?:event|community)\b|\bfetish\s+(?:party|community)\b", re.IGNORECASE
    ),
    "consent": re.compile(
        r"\bconsent\s+is\s+non[-\s]+negotiable\b|\bconsent\s+culture\b|\bmutual\s+consent\b",
        re.IGNORECASE,
    ),
    "inclusive": re.compile(
        r"\binclusive\s+(?:party|dancefloor|space)\b|\bsafe\s+and\s+inclusive\s+dancefloor\b",
        re.IGNORECASE,
    ),
}

DETERMINISTIC_MOOD_PATTERNS: dict[str, re.Pattern[str]] = {
    "energetic": re.compile(r"\bhigh[-\s]+energy\b", re.IGNORECASE),
}


def _deterministic_matches_for_source(
    *,
    source: str,
    text: str,
    tag_type: str,
    patterns: dict[str, re.Pattern[str]],
    confidence: float,
) -> list[EventTaxonomyMatch]:
    matches: list[EventTaxonomyMatch] = []
    for canonical, pattern in patterns.items():
        match = pattern.search(text)
        if match is None:
            continue
        fragment = extract_context_fragment(text, match.start(), match.end())
        if tag_type == "theme" and not is_event_level_theme_evidence(fragment, text):
            continue
        matches.append(
            EventTaxonomyMatch(
                tag_type=tag_type,
                value=canonical,
                evidence=fragment,
                source=source,
                confidence=confidence,
            )
        )
    return matches


def extract_deterministic_event_taxonomy_matches(
    *,
    title: str = "",
    description: str = "",
    lineup_text: str = "",
) -> list[EventTaxonomyMatch]:
    sources = (
        ("title", title, 1.0),
        ("description", description, 0.98),
        ("lineup", lineup_text, 0.95),
    )
    matches: list[EventTaxonomyMatch] = []
    for source, text, confidence in sources:
        if not text:
            continue
        matches.extend(
            _deterministic_matches_for_source(
                source=source,
                text=text,
                tag_type="theme",
                patterns=DETERMINISTIC_THEME_PATTERNS,
                confidence=confidence,
            )
        )
        matches.extend(
            _deterministic_matches_for_source(
                source=source,
                text=text,
                tag_type="mood",
                patterns=DETERMINISTIC_MOOD_PATTERNS,
                confidence=confidence,
            )
        )
    return matches


def event_extraction_rules() -> str:
    controlled_values = "\n".join(
        f"- Allowed {tag_type} values after normalization: {', '.join(values)}."
        for tag_type, values in EVENT_TAG_ALIASES.items()
    )
    return f"""
- Do not extract musical styles or genres. Styles are handled separately by a deterministic music dictionary.
- Return only reusable values from the controlled mood and theme taxonomies.
{controlled_values}
- mood: identify only clearly supported atmosphere categories such as hypnotic, energetic, intimate, or playful.
- theme: identify reusable community or conceptual categories describing this event, party, night, space, guests, or lineup. Ignore artist and organization biography facts.
- Every tag must include a short non-empty evidence phrase copied or closely extracted from the supplied event text.
- Do not output ticket, price, venue amenity, dress-code, date, access, visual-production, or scheduling information as tags.
- Prefer fewer high-confidence reusable tags over descriptive prose.
""".strip()
