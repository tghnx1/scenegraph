from __future__ import annotations

import re
from dataclasses import dataclass

from app.event_style_tags import extract_context_fragment


EVENT_TAG_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "format": {
        "dj-set": ("dj set", "dj sets", "resident dj set", "resident dj sets"),
        "live": (
            "live",
            "live set",
            "live-set",
            "live act",
            "live acts",
            "live pa",
            "live performance",
            "live performances",
        ),
        "b2b": (
            "b2b",
            "b2b set",
            "b2b sets",
            "back-to-back",
            "back to back",
            "back-to-backs",
            "back-to-back sets",
        ),
        "open-decks": ("open decks", "open-decks"),
        "club-night": ("club night", "club nights", "klubnacht"),
        "rave": ("rave",),
        "showcase": ("showcase",),
        "release-party": ("release party", "album release party", "ep release party"),
        "open-mic": ("open mic", "open-mic"),
        "afterhours": ("afterhours", "after hours", "after-hours"),
        "workshop": ("workshop",),
        "festival": ("festival",),
        "exhibition": ("exhibition",),
        "performance": ("performance",),
        "listening-session": ("listening session", "listening-session"),
        "market": ("market",),
        "concert": ("concert",),
        "karaoke": ("karaoke",),
    },
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
    "instrumentation": {
        "vocals": ("vocals", "voice", "vocal"),
        "cello": ("cello",),
        "violin": ("violin", "five-string violin"),
        "electric-guitar": ("electric guitar", "processed electric guitar"),
        "guitar": ("guitar",),
        "bass-guitar": ("bass guitar", "double bass"),
        "piano": ("piano", "yamaha transacoustic piano"),
        "keyboards": ("keyboards", "keyboard"),
        "percussion": ("percussion",),
        "drums": ("drums",),
        "gong": ("gong",),
        "singing-bowls": ("singing bowls", "singing bowl"),
        "chimes": ("chimes",),
        "tuning-forks": ("tuning forks", "tuning fork"),
        "turntables": ("turntables", "turntable", "vinyl turntables"),
        "cdj": ("cdjs", "cdj", "cdj-2000", "pioneer cdj"),
        "synthesizer": ("synthesizer", "synthesizers", "analog synthesizer", "analog synthesizers"),
        "modular-synth": ("modular", "modular synth", "modular synthesizer"),
        "drum-machine": ("drum machine", "drum machines"),
        "hardware": ("hardware", "hardware live"),
        "field-recordings": ("field recordings", "field recording"),
        "saxophone": ("saxophone", "sax"),
        "trombone": ("trombone",),
    },
}

PER_TYPE_LIMITS = {
    "style": 6,
    "format": 3,
    "mood": 3,
    "theme": 4,
    "instrumentation": 5,
    "series": 1,
}

EVENT_TAG_TYPE_PRIORITY = (
    "style",
    "format",
    "theme",
    "mood",
    "instrumentation",
    "series",
)

EVENT_TAG_REJECT_PATTERNS = {
    "format": re.compile(
        r"\b(?:free entry|door tickets?|two floors?|dance floors?|chill areas?|spontaneous|residents?)\b",
        re.IGNORECASE,
    ),
    "mood": re.compile(
        r"\b(?:safe(?:r)? space|queer friendly|respect and consent|charity|casual music enjoyers|no dresscode vibes)\b",
        re.IGNORECASE,
    ),
}

SERIES_INDICATOR_PATTERN = re.compile(
    r"\b(?:series|weekly|monthly|every\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r"|recurring|franchise|edition|chapter|vol(?:ume)?\.?\s*\d+|part\s+[2-9]\d*|returns?|season"
    r"|anniversary\s+edition)\b",
    re.IGNORECASE,
)

SERIES_METADATA_PATTERN = re.compile(
    r"\s*(?:(?:[-:|]|/+)\s*)?(?:"
    r"vol(?:ume)?\.?\s*\d+"
    r"|part\s+\d+"
    r"|season\s+\d+"
    r"|edition\s+\d+"
    r"|anniversary\s+edition"
    r"|(?:first|second|third|fourth|fifth|\d+(?:st|nd|rd|th)?|[a-z]+)\s+edition"
    r")\s*$",
    re.IGNORECASE,
)

SERIES_SCHEDULE_ONLY_PATTERN = re.compile(
    r"^(?:weekly|monthly|recurring|every\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r"|(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+series"
    r"|vol(?:ume)?\.?\s*\d+|part\s+\d+|season\s+\d+|edition)$",
    re.IGNORECASE,
)

FORMAT_LIVE_NEGATIVE_CONTEXT = re.compile(
    r"\blive(?:\s+and\s+direct)?\s+(?:visuals?|projections?|streams?|streaming|broadcasts?|airing|recordings?)\b"
    r"|\bbroadcast\s+live\b",
    re.IGNORECASE,
)

FORMAT_LIVE_POSITIVE_CONTEXT = re.compile(
    r"\b(?:live\s+(?:shows?|sets?|acts?|performances?\s+by|pa)|perform(?:s|ing)?\s+live|hardware\s+live(?:\s+act)?)\b"
    r"|\([^)]*\blive\b[^)]*\)"
    r"|(?:^|\s)[\w.+&'-]+\s+[—-]\s*live(?:\s|$)"
    r"|(?:^|\s)[\w.+&'-]+\s+live$",
    re.IGNORECASE,
)

FORMAT_SHOWCASE_VERB_CONTEXT = re.compile(
    r"\b(?:to|will|shall|can|could|would)\s+showcase\b"
    r"|\bshowcasing\b"
    r"|\bshowcases?\s+(?:their|his|her|its|new)\s+(?:work|music|sound|art)\b",
    re.IGNORECASE,
)

FORMAT_SHOWCASE_NOUN_CONTEXT = re.compile(
    r"\b(?:label|artist|agency|collective|music|album|release)\s+showcase\b"
    r"|\bshowcase\s+(?:night|event|party|series)\b"
    r"|\b(?:first|debut|annual)\s+showcase\b",
    re.IGNORECASE,
)

SERIES_RELATIONSHIP_CONTEXT = (
    r"hosted\s+by\s+{candidate}"
    r"|presented\s+by\s+{candidate}"
    r"|{candidate}\s+(?:pres\.?|presents?)\b"
    r"|(?:@|at|venue:|location:)\s*{candidate}\b"
)

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
        and not (
            tag_type == "format"
            and canonical == "live"
            and text not in EVENT_TAG_ALIASES["format"]["live"]
        )
    ]
    if tag_type == "format" and "live" in values:
        values = [value for value in values if value != "performance"]
    if tag_type == "instrumentation" and "electric-guitar" in values:
        values = [value for value in values if value != "guitar"]
    return values


def is_valid_format_evidence(canonical_value: str, evidence: object) -> bool:
    text = normalize_event_taxonomy_text(evidence)
    if canonical_value == "live":
        if FORMAT_LIVE_NEGATIVE_CONTEXT.search(text):
            return False
        return bool(FORMAT_LIVE_POSITIVE_CONTEXT.search(text))
    if canonical_value == "showcase":
        if FORMAT_SHOWCASE_VERB_CONTEXT.search(text):
            return False
        return bool(FORMAT_SHOWCASE_NOUN_CONTEXT.search(text))
    return True


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


def _series_title_base(title: object) -> str:
    normalized = normalize_event_taxonomy_text(title)
    normalized = re.sub(r"^\[[^\]]+\]\s*", "", normalized)
    normalized = re.sub(
        r"\s+(?:hosted\s+by|pres(?:ented)?\.?\s+by|with|w/|mit|feat\.?|ft\.?)\s+.+$",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    if normalized.count("(") > normalized.count(")"):
        normalized = normalized.split("(", 1)[0]
    normalized = re.sub(r"\s+on\s+two\s+floors?\s*$", "", normalized, flags=re.IGNORECASE)
    normalized = SERIES_METADATA_PATTERN.sub("", normalized).strip(" \t\n\r,.;:|/—–-•")
    return re.sub(r"\s+kinky\s+party\s*$", "", normalized, flags=re.IGNORECASE).strip()


def normalize_series_title_root(title: object) -> str:
    return _series_title_base(title)


def repeated_series_title_roots(
    titles: list[str] | tuple[str, ...],
    *,
    blocked_names: set[str] | None = None,
) -> set[str]:
    blocked = {normalize_event_taxonomy_text(name) for name in (blocked_names or set()) if name}
    title_variants_by_root: dict[str, set[str]] = {}
    for title in titles:
        root = normalize_series_title_root(title)
        if root:
            title_variants_by_root.setdefault(root, set()).add(normalize_event_taxonomy_text(title))
    return {
        root
        for root, title_variants in title_variants_by_root.items()
        if len(title_variants) >= 2
        and len(root) >= 4
        and root not in blocked
        and not re.search(r"\b(?:presents?|pres\.?|hosted\s+by|@|at)\b", root, re.IGNORECASE)
    }


def _series_has_relationship_only_support(candidate: str, evidence: str) -> bool:
    escaped = re.escape(candidate).replace(r"\ ", r"\s+")
    return bool(
        re.search(
            SERIES_RELATIONSHIP_CONTEXT.format(candidate=escaped),
            evidence,
            re.IGNORECASE,
        )
    )


def canonicalize_series(
    value: object,
    *,
    title: object,
    evidence: object,
    repeated_title_root: str = "",
) -> list[str]:
    raw_value = normalize_event_taxonomy_text(value)
    normalized_title = normalize_event_taxonomy_text(title)
    normalized_evidence = normalize_event_taxonomy_text(evidence)
    support_context = " ".join(part for part in (normalized_title, normalized_evidence) if part)
    title_root = _series_title_base(title)
    title_has_recurrence = bool(SERIES_INDICATOR_PATTERN.search(normalized_title))
    repeated_title_support = bool(repeated_title_root and title_root == repeated_title_root)
    if not raw_value or not (
        SERIES_INDICATOR_PATTERN.search(support_context) or repeated_title_support
    ):
        return []
    if raw_value not in support_context:
        return []

    normalized = SERIES_METADATA_PATTERN.sub("", raw_value).strip(" \t\n\r,.;:|/-")
    if len(normalized) < 2 or SERIES_SCHEDULE_ONLY_PATTERN.fullmatch(normalized):
        return []
    if title_root and (title_has_recurrence or repeated_title_support):
        normalized = title_root
    title_supported = title_root == normalized
    explicit_series_support = bool(
        re.search(
            rf"\b(?:series|franchise|monthly\s+night|weekly\s+night|recurring\s+event)\b",
            normalized_evidence,
            re.IGNORECASE,
        )
        and normalized in normalized_evidence
    )
    recurrence_support = explicit_series_support or bool(
        re.search(
            r"\b(?:every\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
            r"|returns?|edition|chapter|vol(?:ume)?\.?\s*\d+|part\s+[2-9]\d*|season)\b",
            normalized_evidence,
            re.IGNORECASE,
        )
        and normalized in normalized_evidence
    )
    if _series_has_relationship_only_support(normalized, normalized_evidence) and not (
        title_supported or explicit_series_support
    ):
        return []
    if not (title_supported or recurrence_support):
        return []
    return [normalized]


DETERMINISTIC_FORMAT_PATTERNS: dict[str, re.Pattern[str]] = {
    "live": re.compile(
        r"\blive\s+(?:shows?|sets?|acts?|pa)\b"
        r"|\bhardware\s+live(?:\s+act)?\b"
        r"|\bperform(?:s|ing)?\s+live\b"
        r"|\([^)]*\blive\b[^)]*\)"
        r"|(?:^|\s)[\w.+&'-]+\s+[—-]\s*live(?:\s|$)",
        re.IGNORECASE,
    ),
    "open-decks": re.compile(r"\bopen[-\s]+decks\b", re.IGNORECASE),
    "dj-set": re.compile(r"\bdj[-\s]+sets?\b", re.IGNORECASE),
    "b2b": re.compile(r"\bb2b\b|\bback[-\s]+to[-\s]+backs?\b", re.IGNORECASE),
    "release-party": re.compile(
        r"\b(?:album\s+|ep\s+|record\s+)?release[-\s]+party\b", re.IGNORECASE
    ),
    "showcase": FORMAT_SHOWCASE_NOUN_CONTEXT,
    "workshop": re.compile(r"\bworkshops?\b", re.IGNORECASE),
    "concert": re.compile(r"\bconcerts?\b", re.IGNORECASE),
    "festival": re.compile(r"\bfestivals?\b", re.IGNORECASE),
}

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
        if tag_type == "format" and not is_valid_format_evidence(canonical, fragment):
            continue
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
    repeated_title_root: str = "",
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
                tag_type="format",
                patterns=DETERMINISTIC_FORMAT_PATTERNS,
                confidence=confidence,
            )
        )
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

    title_root = normalize_series_title_root(title)
    normalized_title = normalize_event_taxonomy_text(title)
    title_has_explicit_series_support = bool(
        title_root != normalized_title
        or re.search(
            r"\b(?:series|weekly|monthly|every\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
            r"|recurring|franchise|chapter|vol(?:ume)?\.?\s*\d+|part\s+[2-9]\d*|returns?)\b",
            normalized_title,
            re.IGNORECASE,
        )
    )
    if title_root and (title_has_explicit_series_support or title_root == repeated_title_root):
        matches.append(
            EventTaxonomyMatch(
                tag_type="series",
                value=title_root,
                evidence=title,
                source="title",
                confidence=1.0,
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
- Return only reusable values from the controlled format, mood, theme, and instrumentation taxonomies.
{controlled_values}
- format: identify event formats such as DJ set, live set, b2b, showcase, release party, workshop, or concert.
- Do not use live for visuals, streams, broadcasts, airings, projections, or recordings. Do not use showcase when it is a verb.
- mood: identify only clearly supported atmosphere categories such as hypnotic, energetic, intimate, or playful.
- theme: identify reusable community or conceptual categories describing this event, party, night, space, guests, or lineup. Ignore artist and organization biography facts.
- instrumentation: identify actual instruments, voices, turntables, CDJs, synthesizers, or music hardware only.
- series: return at most one proper-name series, only with explicit recurrence/franchise evidence such as weekly, edition, vol., returns, chapter, or season. Hosts, promoters, and venues are not series.
- Every tag must include a short non-empty evidence phrase copied or closely extracted from the supplied event text.
- Do not output ticket, price, venue amenity, dress-code, date, access, visual-production, or scheduling information as tags.
- Prefer fewer high-confidence reusable tags over descriptive prose.
""".strip()
