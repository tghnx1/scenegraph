from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import yaml


DEFAULT_RECOMMENDATION_CONFIG_PATH = Path(__file__).with_name("recommendation_config.yaml")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class RecommendationConfig:
    promoter_recommendations: Mapping[str, Any]
    promoter_feedback: Mapping[str, Any]
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class FieldRule:
    expected_type: type
    min_value: float | int | None = None
    max_value: float | int | None = None
    min_inclusive: bool = True
    max_inclusive: bool = True


NON_NEGATIVE_FLOAT = FieldRule(float, 0.0)
ZERO_TO_ONE_FLOAT = FieldRule(float, 0.0, 1.0)
POSITIVE_INT = FieldRule(int, 1)
POSITIVE_FLOAT = FieldRule(float, 0.0, None, min_inclusive=False)
BOOL = FieldRule(bool)


PROMOTER_RECOMMENDATION_SCHEMA: Mapping[str, FieldRule] = {
    "PROMOTER_REC_SEMANTIC_WEIGHT": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_STRENGTH_WEIGHT": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_CO_PLAYED_CONNECTION_WEIGHT": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_MANUAL_CONNECTION_WEIGHT": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_EVENT_SIMILARITY_WEIGHT": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_SCALE_FIT_WEIGHT": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_ACTIVITY_WEIGHT": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_RECENCY_WEIGHT": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_STRENGTH_MATCHED_ARTIST_WEIGHT": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_STRENGTH_EVENT_WEIGHT": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_STRENGTH_MATCHED_ARTIST_CAP": POSITIVE_INT,
    "PROMOTER_REC_STRENGTH_EVENT_CAP": POSITIVE_INT,
    "PROMOTER_REC_WARM_CONNECTION_CAP": POSITIVE_INT,
    "PROMOTER_REC_MANUAL_WARM_CONNECTION_CAP": POSITIVE_INT,
    "PROMOTER_REC_MANUAL_WARM_MIN_ARTIST_SEMANTIC_SCORE": ZERO_TO_ONE_FLOAT,
    "PROMOTER_REC_EVENT_SIMILARITY_COUNT_CAP": POSITIVE_INT,
    "PROMOTER_REC_EVENT_SIMILARITY_MIN_TOTAL_SCORE": ZERO_TO_ONE_FLOAT,
    "PROMOTER_REC_EVENT_SIMILARITY_MIN_EMBEDDING_SCORE": ZERO_TO_ONE_FLOAT,
    "PROMOTER_REC_EVENT_SIMILARITY_PER_PROMOTER_LIMIT": POSITIVE_INT,
    "PROMOTER_REC_EVENT_SIMILARITY_SEMANTIC_ONLY": BOOL,
    "PROMOTER_REC_EVENT_SIMILARITY_SYMBOLIC_WEIGHT": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_EVENT_SIMILARITY_EMBEDDING_WEIGHT": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_EVENT_SIMILARITY_SAME_VENUE_WEIGHT": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_EVENT_SIMILARITY_SHARED_GENRE_WEIGHT": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_EVENT_SIMILARITY_SHARED_LINEUP_WEIGHT": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_EVENT_SIMILARITY_EXTRACTED_GENRE_WEIGHT": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_ACTIVITY_EVENT_CAP": POSITIVE_INT,
    "PROMOTER_REC_WARM_RELEVANT_CONNECTION_MIN": POSITIVE_INT,
    "PROMOTER_REC_WARM_EDGE_STRENGTH_MIN": ZERO_TO_ONE_FLOAT,
    "PROMOTER_REC_WARM_EDGE_STRENGTH_MAX": ZERO_TO_ONE_FLOAT,
    "PROMOTER_REC_EVENT_SIMILARITY_EDGE_STRENGTH_MIN": ZERO_TO_ONE_FLOAT,
    "PROMOTER_REC_EVENT_SIMILARITY_EDGE_STRENGTH_MAX": ZERO_TO_ONE_FLOAT,
    "PROMOTER_REC_SCALE_FIT_ALPHA": POSITIVE_FLOAT,
    "PROMOTER_REC_SCALE_FIT_TAU": POSITIVE_FLOAT,
    "PROMOTER_REC_SQL_CANDIDATE_LIMIT": POSITIVE_INT,
    "PROMOTER_REC_SEMANTIC_ARTIST_POOL_LIMIT": POSITIVE_INT,
    "PROMOTER_REC_SEMANTIC_ARTIST_MIN_SCORE": ZERO_TO_ONE_FLOAT,
    "PROMOTER_REC_EVENT_SIMILARITY_OVERFETCH_MULTIPLIER": POSITIVE_INT,
    "PROMOTER_REC_EVENT_SIMILARITY_OVERFETCH_MIN": POSITIVE_INT,
    "PROMOTER_REC_SOURCE_EVENT_RELEVANCE_GATE_ENABLED": BOOL,
    "PROMOTER_REC_SOURCE_EVENT_RELEVANCE_MIN_EMBEDDING_SCORE": ZERO_TO_ONE_FLOAT,
    "PROMOTER_REC_SOURCE_EVENT_RELEVANCE_TOP_K": POSITIVE_INT,
    "PROMOTER_REC_API_LIMIT_MAX": POSITIVE_INT,
    "PROMOTER_REC_SEGMENT_WARM_SHARE": ZERO_TO_ONE_FLOAT,
    "PROMOTER_REC_SEGMENT_QUOTA_SMALL_SMALL": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_SEGMENT_QUOTA_SMALL_MEDIUM": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_SEGMENT_QUOTA_SMALL_LARGE": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_SEGMENT_QUOTA_MEDIUM_SMALL": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_SEGMENT_QUOTA_MEDIUM_MEDIUM": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_SEGMENT_QUOTA_MEDIUM_LARGE": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_SEGMENT_QUOTA_LARGE_SMALL": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_SEGMENT_QUOTA_LARGE_MEDIUM": NON_NEGATIVE_FLOAT,
    "PROMOTER_REC_SEGMENT_QUOTA_LARGE_LARGE": NON_NEGATIVE_FLOAT,
}


PROMOTER_FEEDBACK_SCHEMA: Mapping[str, FieldRule] = {
    "PROMOTER_FEEDBACK_EXACT_POSITIVE_BOOST": NON_NEGATIVE_FLOAT,
    "PROMOTER_FEEDBACK_SIMILAR_POSITIVE_BOOST": NON_NEGATIVE_FLOAT,
    "PROMOTER_FEEDBACK_MAX_TOTAL_BOOST": NON_NEGATIVE_FLOAT,
    "PROMOTER_FEEDBACK_SIMILARITY_MIN": ZERO_TO_ONE_FLOAT,
    "PROMOTER_FEEDBACK_SIMILAR_PROMOTER_LIMIT": POSITIVE_INT,
    "PROMOTER_PROFILE_EVENT_LIMIT": POSITIVE_INT,
    "SHARED_ARTISTS_WEIGHT": NON_NEGATIVE_FLOAT,
    "SHARED_GENRES_TAGS_WEIGHT": NON_NEGATIVE_FLOAT,
    "SIMILAR_EVENTS_WEIGHT": NON_NEGATIVE_FLOAT,
    "SHARED_VENUES_WEIGHT": NON_NEGATIVE_FLOAT,
}


REQUIRED_LEGACY_ALIASES: Mapping[str, str] = {
    "PROMOTER_REC_WARM_NETWORK_WEIGHT": "PROMOTER_REC_CO_PLAYED_CONNECTION_WEIGHT",
    "PROMOTER_REC_EVENT_SIMILARITY_EXTRACTED_STYLE_WEIGHT": (
        "PROMOTER_REC_EVENT_SIMILARITY_EXTRACTED_GENRE_WEIGHT"
    ),
}


SEGMENT_QUOTA_ROWS: tuple[tuple[str, ...], ...] = (
    (
        "PROMOTER_REC_SEGMENT_QUOTA_SMALL_SMALL",
        "PROMOTER_REC_SEGMENT_QUOTA_SMALL_MEDIUM",
        "PROMOTER_REC_SEGMENT_QUOTA_SMALL_LARGE",
    ),
    (
        "PROMOTER_REC_SEGMENT_QUOTA_MEDIUM_SMALL",
        "PROMOTER_REC_SEGMENT_QUOTA_MEDIUM_MEDIUM",
        "PROMOTER_REC_SEGMENT_QUOTA_MEDIUM_LARGE",
    ),
    (
        "PROMOTER_REC_SEGMENT_QUOTA_LARGE_SMALL",
        "PROMOTER_REC_SEGMENT_QUOTA_LARGE_MEDIUM",
        "PROMOTER_REC_SEGMENT_QUOTA_LARGE_LARGE",
    ),
)


EDGE_STRENGTH_PAIRS: tuple[tuple[str, str], ...] = (
    ("PROMOTER_REC_WARM_EDGE_STRENGTH_MIN", "PROMOTER_REC_WARM_EDGE_STRENGTH_MAX"),
    (
        "PROMOTER_REC_EVENT_SIMILARITY_EDGE_STRENGTH_MIN",
        "PROMOTER_REC_EVENT_SIMILARITY_EDGE_STRENGTH_MAX",
    ),
)


def load_recommendation_config(
    path: str | Path = DEFAULT_RECOMMENDATION_CONFIG_PATH,
) -> RecommendationConfig:
    with Path(path).open("r", encoding="utf-8") as config_file:
        data = yaml.safe_load(config_file)

    if not isinstance(data, dict):
        raise ConfigError("Recommendation config must be a mapping")

    _require_exact_keys(data, {"promoter_recommendations", "promoter_feedback", "metadata"}, "config")

    promoter_recommendations = _require_mapping(
        data["promoter_recommendations"],
        "promoter_recommendations",
    )
    promoter_feedback = _require_mapping(data["promoter_feedback"], "promoter_feedback")
    metadata = _require_mapping(data["metadata"], "metadata")

    _validate_schema(
        promoter_recommendations,
        PROMOTER_RECOMMENDATION_SCHEMA,
        "promoter_recommendations",
    )
    _validate_schema(promoter_feedback, PROMOTER_FEEDBACK_SCHEMA, "promoter_feedback")
    _validate_segment_quota_rows(promoter_recommendations)
    _validate_edge_strength_ranges(promoter_recommendations)
    _validate_metadata(metadata)

    return RecommendationConfig(
        promoter_recommendations=_freeze_mapping(promoter_recommendations),
        promoter_feedback=_freeze_mapping(promoter_feedback),
        metadata=_freeze_mapping(metadata),
    )


def _require_mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{context} must be a mapping")
    return value


def _require_exact_keys(value: Mapping[str, Any], required: set[str], context: str) -> None:
    actual = set(value)
    missing = sorted(required - actual)
    extra = sorted(actual - required)
    if missing:
        raise ConfigError(f"{context} missing keys: {missing}")
    if extra:
        raise ConfigError(f"{context} extra keys: {extra}")


def _validate_schema(
    values: Mapping[str, Any],
    schema: Mapping[str, FieldRule],
    context: str,
) -> None:
    _require_exact_keys(values, set(schema), context)
    for key, rule in schema.items():
        _validate_field(key, values[key], rule, context)


def _validate_field(key: str, value: Any, rule: FieldRule, context: str) -> None:
    if type(value) is not rule.expected_type:
        raise ConfigError(
            f"{context}.{key} must be {rule.expected_type.__name__}, "
            f"got {type(value).__name__}"
        )
    if rule.min_value is not None:
        if rule.min_inclusive and value < rule.min_value:
            raise ConfigError(f"{context}.{key} must be >= {rule.min_value}")
        if not rule.min_inclusive and value <= rule.min_value:
            raise ConfigError(f"{context}.{key} must be > {rule.min_value}")
    if rule.max_value is not None:
        if rule.max_inclusive and value > rule.max_value:
            raise ConfigError(f"{context}.{key} must be <= {rule.max_value}")
        if not rule.max_inclusive and value >= rule.max_value:
            raise ConfigError(f"{context}.{key} must be < {rule.max_value}")


def _validate_segment_quota_rows(values: Mapping[str, Any]) -> None:
    for row in SEGMENT_QUOTA_ROWS:
        total = sum(values[key] for key in row)
        if total <= 0:
            row_name = row[0].removeprefix("PROMOTER_REC_SEGMENT_QUOTA_").split("_")[0]
            raise ConfigError(f"segment quota row {row_name.lower()} total must be > 0")


def _validate_edge_strength_ranges(values: Mapping[str, Any]) -> None:
    for min_key, max_key in EDGE_STRENGTH_PAIRS:
        if values[min_key] > values[max_key]:
            raise ConfigError(f"{min_key} must be <= {max_key}")


def _validate_metadata(metadata: Mapping[str, Any]) -> None:
    _require_exact_keys(metadata, {"legacy_aliases"}, "metadata")
    legacy_aliases = _require_mapping(metadata["legacy_aliases"], "metadata.legacy_aliases")
    _require_exact_keys(legacy_aliases, set(REQUIRED_LEGACY_ALIASES), "metadata.legacy_aliases")
    for alias, target in REQUIRED_LEGACY_ALIASES.items():
        actual_target = legacy_aliases[alias]
        if actual_target != target:
            raise ConfigError(f"metadata.legacy_aliases.{alias} must point to {target}")


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    frozen: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, dict):
            frozen[key] = _freeze_mapping(item)
        else:
            frozen[key] = item
    return MappingProxyType(frozen)
