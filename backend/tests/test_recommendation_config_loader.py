from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import MappingProxyType

import pytest
import yaml

from app.recommendation_config_loader import (
    DEFAULT_RECOMMENDATION_CONFIG_PATH,
    ConfigError,
    load_recommendation_config,
)


def test_loads_canonical_config() -> None:
    config = load_recommendation_config()

    assert config.promoter_recommendations["PROMOTER_REC_SEMANTIC_WEIGHT"] == 0.25
    assert config.promoter_recommendations["PROMOTER_REC_API_LIMIT_MAX"] == 50
    assert config.promoter_feedback["PROMOTER_FEEDBACK_EXACT_POSITIVE_BOOST"] == 0.10
    assert config.promoter_feedback["PROMOTER_PROFILE_EVENT_LIMIT"] == 20
    assert (
        config.metadata["legacy_aliases"]["PROMOTER_REC_WARM_NETWORK_WEIGHT"]
        == "PROMOTER_REC_CO_PLAYED_CONNECTION_WEIGHT"
    )


def test_returns_immutable_mappings() -> None:
    config = load_recommendation_config()

    assert isinstance(config.promoter_recommendations, MappingProxyType)
    assert isinstance(config.promoter_feedback, MappingProxyType)
    assert isinstance(config.metadata, MappingProxyType)
    assert isinstance(config.metadata["legacy_aliases"], MappingProxyType)

    with pytest.raises(TypeError):
        config.promoter_recommendations["PROMOTER_REC_API_LIMIT_MAX"] = 20
    with pytest.raises(TypeError):
        config.metadata["legacy_aliases"]["PROMOTER_REC_WARM_NETWORK_WEIGHT"] = "x"


def test_legacy_aliases_are_metadata_only() -> None:
    config = load_recommendation_config()

    assert "PROMOTER_REC_WARM_NETWORK_WEIGHT" not in config.promoter_recommendations
    assert (
        "PROMOTER_REC_EVENT_SIMILARITY_EXTRACTED_STYLE_WEIGHT"
        not in config.promoter_recommendations
    )
    assert "PROMOTER_REC_WARM_NETWORK_WEIGHT" in config.metadata["legacy_aliases"]


def test_missing_key_rejected(tmp_path: Path) -> None:
    config_data = _canonical_config_data()
    del config_data["promoter_recommendations"]["PROMOTER_REC_API_LIMIT_MAX"]

    with pytest.raises(ConfigError, match="missing keys"):
        load_recommendation_config(_write_config(tmp_path, config_data))


def test_extra_key_rejected(tmp_path: Path) -> None:
    config_data = _canonical_config_data()
    config_data["promoter_recommendations"]["NOT_A_REAL_KEY"] = 1

    with pytest.raises(ConfigError, match="extra keys"):
        load_recommendation_config(_write_config(tmp_path, config_data))


def test_wrong_type_rejected(tmp_path: Path) -> None:
    config_data = _canonical_config_data()
    config_data["promoter_recommendations"]["PROMOTER_REC_API_LIMIT_MAX"] = "50"

    with pytest.raises(ConfigError, match="PROMOTER_REC_API_LIMIT_MAX"):
        load_recommendation_config(_write_config(tmp_path, config_data))


def test_invalid_range_rejected(tmp_path: Path) -> None:
    config_data = _canonical_config_data()
    config_data["promoter_recommendations"]["PROMOTER_REC_API_LIMIT_MAX"] = 0

    with pytest.raises(ConfigError, match="PROMOTER_REC_API_LIMIT_MAX"):
        load_recommendation_config(_write_config(tmp_path, config_data))


def test_segment_quota_row_zero_rejected(tmp_path: Path) -> None:
    config_data = _canonical_config_data()
    config_data["promoter_recommendations"]["PROMOTER_REC_SEGMENT_QUOTA_SMALL_SMALL"] = 0.0
    config_data["promoter_recommendations"]["PROMOTER_REC_SEGMENT_QUOTA_SMALL_MEDIUM"] = 0.0
    config_data["promoter_recommendations"]["PROMOTER_REC_SEGMENT_QUOTA_SMALL_LARGE"] = 0.0

    with pytest.raises(ConfigError, match="segment quota row small"):
        load_recommendation_config(_write_config(tmp_path, config_data))


def test_edge_strength_min_above_max_rejected(tmp_path: Path) -> None:
    config_data = _canonical_config_data()
    config_data["promoter_recommendations"]["PROMOTER_REC_DIRECT_EDGE_STRENGTH_MIN"] = 1.0
    config_data["promoter_recommendations"]["PROMOTER_REC_DIRECT_EDGE_STRENGTH_MAX"] = 0.5

    with pytest.raises(ConfigError, match="PROMOTER_REC_DIRECT_EDGE_STRENGTH_MIN"):
        load_recommendation_config(_write_config(tmp_path, config_data))


def test_wrong_legacy_alias_target_rejected(tmp_path: Path) -> None:
    config_data = _canonical_config_data()
    config_data["metadata"]["legacy_aliases"]["PROMOTER_REC_WARM_NETWORK_WEIGHT"] = (
        "PROMOTER_REC_DIRECT_CONNECTION_WEIGHT"
    )

    with pytest.raises(ConfigError, match="PROMOTER_REC_WARM_NETWORK_WEIGHT"):
        load_recommendation_config(_write_config(tmp_path, config_data))


def _canonical_config_data() -> dict:
    with DEFAULT_RECOMMENDATION_CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        return deepcopy(yaml.safe_load(config_file))


def _write_config(tmp_path: Path, config_data: dict) -> Path:
    config_path = tmp_path / "recommendation_config.yaml"
    with config_path.open("w", encoding="utf-8") as config_file:
        yaml.safe_dump(config_data, config_file, sort_keys=False)
    return config_path
