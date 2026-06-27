import os
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://scenegraph:change-me@db:5432/scenegraph")

from app.embeddings import EmbeddingConfig, embedding_text_hash, embedding_vector_literal


def test_embedding_text_hash_normalizes_whitespace():
    assert embedding_text_hash("Night\n\nMusic") == embedding_text_hash("  Night Music  ")


def test_embedding_vector_literal_formats_for_pgvector():
    assert embedding_vector_literal([0.1, 2.0, -3.5]) == "[0.1,2,-3.5]"


def test_embedding_config_reads_env(monkeypatch):
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
    monkeypatch.setenv("OPENAI_EMBEDDING_DIMENSIONS", "1024")

    config = EmbeddingConfig.from_env()

    assert config.model == "text-embedding-3-large"
    assert config.provider_model_key == "openai:text-embedding-3-large"
    assert config.dimensions == 1024


def test_embedding_config_requires_model(monkeypatch):
    monkeypatch.delenv("OPENAI_EMBEDDING_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_EMBEDDING_DIMENSIONS", "1024")

    with pytest.raises(ValueError, match="OPENAI_EMBEDDING_MODEL"):
        EmbeddingConfig.from_env()


def test_embedding_config_requires_dimensions(monkeypatch):
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
    monkeypatch.delenv("OPENAI_EMBEDDING_DIMENSIONS", raising=False)

    with pytest.raises(ValueError, match="OPENAI_EMBEDDING_DIMENSIONS"):
        EmbeddingConfig.from_env()
