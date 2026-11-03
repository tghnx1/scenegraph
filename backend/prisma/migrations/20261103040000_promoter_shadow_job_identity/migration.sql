ALTER TABLE promoter_role_shadow_result ADD COLUMN recommendation_job_id UUID;
CREATE UNIQUE INDEX promoter_role_shadow_result_job_id_idx
    ON promoter_role_shadow_result(recommendation_job_id)
    WHERE recommendation_job_id IS NOT NULL;
