CREATE UNIQUE INDEX recommendation_jobs_active_promoter_unique_idx
ON recommendation_jobs (user_id, artist_id, job_type, params_hash)
WHERE job_type = 'artist_promoters'
  AND status IN ('queued', 'running');
