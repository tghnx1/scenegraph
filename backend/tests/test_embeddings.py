import os

os.environ.setdefault("DATABASE_URL", "postgresql://scenegraph:change-me@db:5432/scenegraph")

from app.embeddings import EmbeddingConfig, cosine_similarity, embedding_text_hash


def test_embedding_text_hash_normalizes_whitespace():
    assert embedding_text_hash("Night\n\nMusic") == embedding_text_hash("  Night Music  ")


def test_cosine_similarity_scores_related_vectors_higher():
    source = [1.0, 0.0, 0.0]
    close = [0.9, 0.1, 0.0]
    far = [0.0, 1.0, 0.0]

    assert cosine_similarity(source, close) > cosine_similarity(source, far)


def test_embedding_config_reads_env(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
    monkeypatch.setenv("OPENAI_EMBEDDING_DIMENSIONS", "1024")

    config = EmbeddingConfig.from_env()

    assert config.provider == "openai"
    assert config.model == "text-embedding-3-large"
    assert config.provider_model_key == "openai:text-embedding-3-large"
    assert config.dimensions == 1024


def test_embedding_config_reads_azure_env(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "azure")
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "scenegraph-embedding-small")
    monkeypatch.delenv("OPENAI_EMBEDDING_DIMENSIONS", raising=False)

    config = EmbeddingConfig.from_env()

    assert config.provider == "azure"
    assert config.model == "scenegraph-embedding-small"
    assert config.provider_model_key == "azure:scenegraph-embedding-small"
    assert config.dimensions is None
