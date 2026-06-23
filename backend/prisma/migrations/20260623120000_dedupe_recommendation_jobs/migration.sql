DELETE FROM "recommendation_jobs" target
USING (
    SELECT ctid,
           row_number() OVER (
               PARTITION BY user_id, artist_id, job_type, params_hash
               ORDER BY created_at DESC, id DESC
           ) AS rn
    FROM "recommendation_jobs"
) duplicates
WHERE target.ctid = duplicates.ctid
  AND duplicates.rn > 1;
