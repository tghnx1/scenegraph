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
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
    monkeypatch.setenv("OPENAI_EMBEDDING_DIMENSIONS", "1024")

    config = EmbeddingConfig.from_env()

    assert config.model == "text-embedding-3-large"
    assert config.dimensions == 1024
