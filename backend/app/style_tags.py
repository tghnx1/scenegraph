from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any


STYLE_ALIASES: dict[str, tuple[str, ...]] = {
    "acid": ("acid",),
    "acid house": ("acid house",),
    "acid techno": ("acid techno",),
    "acid trance": ("acid trance",),
    "afrobeat": ("afrobeat", "afro beat"),
    "afro house": ("afro house",),
    "amapiano": ("amapiano",),
    "ambient": ("ambient",),
    "ambient house": ("ambient house",),
    "ambient techno": ("ambient techno",),
    "art pop": ("art pop",),
    "balearic": ("balearic",),
    "bass": ("bass", "bass music"),
    "bass house": ("bass house",),
    "bassline": ("bassline",),
    "berlin school": ("berlin school",),
    "big room": ("big room",),
    "big room house": ("big room house",),
    "blues": ("blues",),
    "boogie": ("boogie",),
    "boom bap": ("boom bap",),
    "breakbeat": ("breakbeat", "breakbeats", "breaks"),
    "breakcore": ("breakcore",),
    "chicago house": ("chicago house",),
    "chicago techno": ("chicago techno",),
    "chug": ("chug", "chuggy"),
    "classical": ("classical",),
    "cold wave": ("cold wave", "coldwave"),
    "country": ("country",),
    "cosmic disco": ("cosmic disco",),
    "dancehall": ("dancehall",),
    "dark disco": ("dark disco",),
    "dark wave": ("dark wave", "darkwave"),
    "death metal": ("death metal",),
    "deep house": ("deep house",),
    "deep techno": ("deep techno",),
    "detroit techno": ("detroit techno",),
    "digital hardcore": ("digital hardcore",),
    "disco": ("disco",),
    "downtempo": ("downtempo", "down tempo"),
    "dream house": ("dream house",),
    "drone": ("drone",),
    "drum and bass": (
        "drum and bass",
        "drum & bass",
        "drum n bass",
        "drum 'n' bass",
        "drum n' bass",
        "dnb",
        "d&b",
    ),
    "dub": ("dub",),
    "dub techno": ("dub techno",),
    "dubstep": ("dubstep",),
    "ebm": ("ebm", "electronic body music", "body music"),
    "electro": ("electro",),
    "electro house": ("electro house",),
    "electro-industrial": ("electro-industrial", "electro industrial"),
    "electro-pop": ("electro-pop", "electro pop", "electropop"),
    "electroclash": ("electroclash",),
    "electronica": ("electronica",),
    "emo": ("emo",),
    "euro trance": ("euro trance", "eurotrance"),
    "eurodance": ("eurodance",),
    "experimental": ("experimental",),
    "flamenco": ("flamenco",),
    "folk": ("folk",),
    "footwork": ("footwork",),
    "freestyle": ("freestyle",),
    "french house": ("french house",),
    "funk": ("funk",),
    "funky house": ("funky house",),
    "future garage": ("future garage",),
    "future house": ("future house",),
    "gabber": ("gabber",),
    "garage": ("garage",),
    "ghetto house": ("ghetto house",),
    "ghettotech": ("ghettotech", "ghetto tech"),
    "gqom": ("gqom",),
    "grunge": ("grunge",),
    "grime": ("grime",),
    "hard rock": ("hard rock",),
    "hard house": ("hard house",),
    "hard techno": ("hard techno",),
    "hard trance": ("hard trance",),
    "hardcore": ("hardcore",),
    "hardcore punk": ("hardcore punk",),
    "hardgroove": ("hardgroove",),
    "hi-nrg": ("hi-nrg", "hi nrg", "high nrg"),
    "hip hop": ("hip hop", "hip-hop", "hiphop"),
    "house": ("house",),
    "hypnotic techno": ("hypnotic techno",),
    "idm": ("idm",),
    "indie dance": ("indie dance",),
    "indie pop": ("indie pop",),
    "indie rock": ("indie rock",),
    "industrial": ("industrial",),
    "industrial techno": ("industrial techno",),
    "italo": ("italo",),
    "italo disco": ("italo disco",),
    "italo house": ("italo house",),
    "jazz": ("jazz",),
    "jazz house": ("jazz house",),
    "jungle": ("jungle",),
    "krautrock": ("krautrock",),
    "latin house": ("latin house",),
    "leftfield": ("leftfield",),
    "lo-fi house": ("lo-fi house", "lo fi house", "lofi house"),
    "makina": ("makina",),
    "melodic techno": ("melodic techno",),
    "metal": ("metal",),
    "microhouse": ("microhouse", "micro house"),
    "minimal": ("minimal",),
    "minimal house": ("minimal house",),
    "minimal techno": ("minimal techno",),
    "minimal wave": ("minimal wave",),
    "neo soul": ("neo soul", "neo-soul"),
    "new beat": ("new beat",),
    "new wave": ("new wave",),
    "noise": ("noise",),
    "noise rock": ("noise rock",),
    "nu disco": ("nu disco", "nu-disco", "nudisco"),
    "organic house": ("organic house",),
    "percussive": ("percussive",),
    "pop": ("pop",),
    "pop punk": ("pop punk",),
    "post-hardcore": ("post-hardcore", "post hardcore"),
    "post-industrial": ("post-industrial", "post industrial"),
    "post-punk": ("post-punk", "post punk"),
    "post-rock": ("post-rock", "post rock"),
    "progressive": ("progressive",),
    "progressive house": ("progressive house",),
    "progressive trance": ("progressive trance",),
    "proto-techno": ("proto-techno", "proto techno"),
    "psychedelic": ("psychedelic",),
    "psychedelic rock": ("psychedelic rock", "psych rock"),
    "psytrance": ("psytrance", "psy trance"),
    "punk": ("punk",),
    "r&b": ("r&b", "rnb", "rhythm and blues"),
    "rap": ("rap",),
    "rave": ("rave",),
    "reggae": ("reggae",),
    "rock": ("rock",),
    "ska": ("ska",),
    "schranz": ("schranz",),
    "slow techno": ("slow techno",),
    "soul": ("soul",),
    "speed garage": ("speed garage",),
    "synth punk": ("synth punk", "synth-punk"),
    "synth-pop": ("synth-pop", "synth pop"),
    "synthwave": ("synthwave", "synth wave"),
    "tech house": ("tech house",),
    "techno": ("techno",),
    "trance": ("trance",),
    "trap": ("trap",),
    "tribal": ("tribal",),
    "tribal house": ("tribal house",),
    "tribal techno": ("tribal techno",),
    "trip hop": ("trip hop", "trip-hop"),
    "uk bass": ("uk bass",),
    "uk funky": ("uk funky",),
    "uk garage": ("uk garage", "ukg"),
    "vaporwave": ("vaporwave", "vapor wave"),
    "wave": ("wave",),
    "witch house": ("witch house",),
}


def normalize_style_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def style_alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias).replace(r"\ ", r"[\s\-]+")
    return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)


STYLE_PATTERNS = {
    tag: tuple(style_alias_pattern(alias) for alias in aliases)
    for tag, aliases in STYLE_ALIASES.items()
}

PARENT_STYLE_TAGS: dict[str, tuple[str, ...]] = {
    "acid house": ("acid", "house"),
    "acid techno": ("acid", "techno"),
    "acid trance": ("acid", "trance"),
    "afro house": ("house",),
    "ambient house": ("ambient", "house"),
    "ambient techno": ("ambient", "techno"),
    "art pop": ("pop",),
    "bass house": ("bass", "house"),
    "big room house": ("big room", "house"),
    "chicago house": ("house",),
    "chicago techno": ("techno",),
    "cosmic disco": ("disco",),
    "dark disco": ("disco",),
    "dark wave": ("wave",),
    "death metal": ("metal",),
    "deep house": ("house",),
    "deep techno": ("techno",),
    "detroit techno": ("techno",),
    "digital hardcore": ("hardcore",),
    "drum and bass": ("bass",),
    "dub techno": ("dub", "techno"),
    "electro house": ("electro", "house"),
    "electro-industrial": ("electro", "industrial"),
    "electro-pop": ("electro", "pop"),
    "euro trance": ("trance",),
    "french house": ("house",),
    "funky house": ("funk", "house"),
    "future garage": ("garage",),
    "future house": ("house",),
    "ghetto house": ("house",),
    "hard rock": ("rock",),
    "hard house": ("house",),
    "hard techno": ("techno",),
    "hard trance": ("trance",),
    "hardcore punk": ("hardcore", "punk"),
    "hypnotic techno": ("techno",),
    "indie pop": ("pop",),
    "indie rock": ("rock",),
    "industrial techno": ("industrial", "techno"),
    "italo disco": ("disco", "italo"),
    "italo house": ("house", "italo"),
    "jazz house": ("house", "jazz"),
    "latin house": ("house",),
    "lo-fi house": ("house",),
    "melodic techno": ("techno",),
    "minimal house": ("house", "minimal"),
    "minimal techno": ("minimal", "techno"),
    "minimal wave": ("minimal", "wave"),
    "neo soul": ("soul",),
    "new wave": ("wave",),
    "noise rock": ("noise", "rock"),
    "nu disco": ("disco",),
    "organic house": ("house",),
    "pop punk": ("pop", "punk"),
    "post-hardcore": ("hardcore",),
    "post-industrial": ("industrial",),
    "progressive house": ("house", "progressive"),
    "progressive trance": ("progressive", "trance"),
    "psychedelic rock": ("psychedelic", "rock"),
    "psytrance": ("trance",),
    "slow techno": ("techno",),
    "speed garage": ("garage",),
    "synth punk": ("punk",),
    "synth-pop": ("pop",),
    "synthwave": ("wave",),
    "tech house": ("house",),
    "tribal house": ("house", "tribal"),
    "tribal techno": ("techno", "tribal"),
    "uk garage": ("garage",),
    "vaporwave": ("wave",),
}


def suppress_parent_style_tags(tags: Iterable[str]) -> list[str]:
    tag_set = set(tags)
    for specific_tag, parent_tags in PARENT_STYLE_TAGS.items():
        if specific_tag in tag_set:
            tag_set.difference_update(parent_tags)
    return sorted(tag_set)


def canonicalize_style_tags(value: Any) -> list[str]:
    text = normalize_style_text(value).lower()
    if not text:
        return []

    return suppress_parent_style_tags(
        tag
        for tag, patterns in STYLE_PATTERNS.items()
        if any(pattern.search(text) for pattern in patterns)
    )


def extract_style_tags(value: Any) -> list[str]:
    return canonicalize_style_tags(value)


def style_overlap_score(source_tags: list[str], candidate_tags: list[str]) -> float:
    if not source_tags or not candidate_tags:
        return 0.0

    source_set = set(source_tags)
    candidate_set = set(candidate_tags)
    overlap = source_set & candidate_set
    union = source_set | candidate_set
    return len(overlap) / len(union)
