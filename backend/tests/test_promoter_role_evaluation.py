from app.promoter_role_evaluation import ReviewedRole, evaluate_roles


def test_unknown_organizer_reduces_recall_below_gate():
    quality = evaluate_roles((ReviewedRole(True, "organizer"), ReviewedRole(True, "unknown"), ReviewedRole(False, "venue")))
    assert (quality.true_positive, quality.false_positive, quality.false_negative, quality.unknown) == (1, 0, 1, 1)
    assert quality.precision == 1
    assert quality.recall == 0.5
    assert not quality.passes


def test_both_metrics_must_reach_seventy_percent():
    passing = tuple([ReviewedRole(True, "both")] * 7 + [ReviewedRole(True, "unknown")] * 3 + [ReviewedRole(False, "organizer")] * 3)
    quality = evaluate_roles(passing)
    assert quality.precision == 0.7
    assert quality.recall == 0.7
    assert quality.passes


def test_metrics_below_seventy_percent_fail_independently():
    low_precision = tuple([ReviewedRole(True, "organizer")] * 6 + [ReviewedRole(False, "organizer")] * 4)
    low_recall = tuple([ReviewedRole(True, "organizer")] * 6 + [ReviewedRole(True, "unknown")] * 4 + [ReviewedRole(False, "venue")])
    assert not evaluate_roles(low_precision).passes
    assert not evaluate_roles(low_recall).passes


def test_empty_denominators_never_pass():
    assert not evaluate_roles(()).passes
    assert evaluate_roles((ReviewedRole(False, "venue"),)).precision is None


def test_positive_only_sample_does_not_satisfy_release_gate():
    quality = evaluate_roles((ReviewedRole(True, "organizer"),))
    assert quality.precision == 1 and quality.recall == 1
    assert not quality.passes
