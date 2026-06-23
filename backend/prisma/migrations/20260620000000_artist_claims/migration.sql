ALTER TABLE users
ADD COLUMN IF NOT EXISTS artist_id BIGINT REFERENCES artists(id);

CREATE TABLE IF NOT EXISTS artist_claims (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id),
  artist_id BIGINT NOT NULL REFERENCES artists(id),
  reason TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'approved', 'rejected')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  decided_at TIMESTAMPTZ,
  decided_by BIGINT REFERENCES users(id)
);