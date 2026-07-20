ALTER TABLE artist_claims
ADD COLUMN IF NOT EXISTS instagram_url TEXT;

ALTER TABLE artists
ALTER COLUMN ra_artist_id DROP NOT NULL;
