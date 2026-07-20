CREATE UNIQUE INDEX IF NOT EXISTS "artist_claims_active_artist_unique_idx"
ON artist_claims (artist_id)
WHERE status IN ('pending', 'approved');

CREATE UNIQUE INDEX IF NOT EXISTS "artist_claims_active_instagram_unique_idx"
ON artist_claims (LOWER(BTRIM(instagram_url)))
WHERE instagram_url IS NOT NULL
  AND status IN ('pending', 'approved');
