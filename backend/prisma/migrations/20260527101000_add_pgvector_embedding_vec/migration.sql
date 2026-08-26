CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE IF EXISTS entity_embeddings
ADD COLUMN IF NOT EXISTS embedding_vec vector(1536);

UPDATE entity_embeddings
SET embedding_vec = embedding::vector
WHERE embedding_vec IS NULL
  AND dimensions = 1536;

CREATE INDEX IF NOT EXISTS entity_embeddings_vector_hnsw_cosine_idx
ON entity_embeddings
USING hnsw (embedding_vec vector_cosine_ops)
WHERE embedding_vec IS NOT NULL;

CREATE INDEX IF NOT EXISTS entity_embeddings_vector_lookup_idx
ON entity_embeddings (entity_type, model, dimensions, entity_id)
WHERE embedding_vec IS NOT NULL;
