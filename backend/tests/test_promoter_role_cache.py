from app.promoter_role_runtime import RoleRuntimeContext
from app.recommendations.jobs import _params_hash, role_aware_params_hash
from app.recommendations import role_aware
import pytest


def test_role_cache_keys_isolate_revision_mode_and_configuration():
    params = {"limit": 200, "debug": False}
    original = role_aware_params_hash(params, RoleRuntimeContext("off", 0, None))
    assert original == _params_hash(params)

    keys = {
        original,
        role_aware_params_hash(params, RoleRuntimeContext("off", 1, None)),
        role_aware_params_hash(params, RoleRuntimeContext("enforce", 1, "one")),
        role_aware_params_hash(params, RoleRuntimeContext("enforce", 2, "one")),
        role_aware_params_hash(params, RoleRuntimeContext("enforce", 1, "two")),
    }
    assert len(keys) == 5


def test_recommendation_calculation_rejects_changed_revision(monkeypatch):
    contexts = iter([RoleRuntimeContext("off", 0, None), RoleRuntimeContext("off", 1, None)])
    monkeypatch.setattr(role_aware, "resolve_runtime_context", lambda *args, **kwargs: next(contexts))
    monkeypatch.setattr(role_aware, "build_artist_promoter_recommendation_response", lambda *args, **kwargs: object())
    with pytest.raises(RuntimeError, match="changed during"):
        role_aware.build_role_aware_recommendations(object(), artist_id=1, limit=10, debug=False, user_id=1)
