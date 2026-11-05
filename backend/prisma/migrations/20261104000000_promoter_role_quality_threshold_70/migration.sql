-- Keep existing immutable reviews and lower both thresholds to the agreed 70%.
ALTER TABLE promoter_role_quality_review
  DROP CONSTRAINT promoter_role_quality_review_check2,
  DROP CONSTRAINT promoter_role_quality_review_check3,
  ADD CONSTRAINT promoter_role_quality_review_precision_70_check
    CHECK (true_positive::bigint * 10 >= (true_positive::bigint + false_positive) * 7),
  ADD CONSTRAINT promoter_role_quality_review_recall_70_check
    CHECK (true_positive::bigint * 10 >= (true_positive::bigint + false_negative) * 7);
