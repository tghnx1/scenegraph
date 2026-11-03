ALTER TABLE promoter_role_backfill_item
    ADD COLUMN input_tokens BIGINT CHECK (input_tokens >= 0),
    ADD COLUMN output_tokens BIGINT CHECK (output_tokens >= 0);
