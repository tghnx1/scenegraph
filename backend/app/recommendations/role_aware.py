"""Apply an approved promoter-role rollout to one recommendation calculation."""

from psycopg import Connection

from app.promoter_role_relation import role_filtered_relation
from app.promoter_role_runtime import resolve_runtime_context
from app.recommendations.services import build_artist_promoter_recommendation_response
from app.schemas import PromoterRecommendationResponse


def build_role_aware_recommendations(
    connection: Connection, *, artist_id: int, limit: int, debug: bool, user_id: int
) -> PromoterRecommendationResponse:
    context = resolve_runtime_context(connection, user_id=user_id)
    arguments = dict(artist_id=artist_id, limit=limit, debug=debug, user_id=user_id)
    if context.mode == "enforce":
        assert context.config_hash is not None
        with role_filtered_relation(connection, context.config_hash):
            result = build_artist_promoter_recommendation_response(connection, **arguments)
    else:
        result = build_artist_promoter_recommendation_response(connection, **arguments)
    # Lock before returning, so a result built across a revision change is not used.
    if resolve_runtime_context(connection, user_id=user_id, lock=True) != context:
        raise RuntimeError("Promoter classification changed during recommendation calculation; retry")
    return result
