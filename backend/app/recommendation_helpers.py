from __future__ import annotations

from fastapi import HTTPException
from psycopg import Connection

from app.embeddings import EmbeddingConfig, EntityType, rank_similar_embeddings
from app.recommendation_scoring import (
    SemanticArtistTagScoringConfig,
    semantic_artist_scoring_from_env,
    semantic_artist_tag_scoring_from_env,
)
from app.schemas import EntityKind, RecommendationFeedbackItem
from app.style_tags import extract_style_tags, style_overlap_score

# Build stable graph node ids used across graph payloads.
def graph_node_id(node_type: str, entity_id: int) -> str:
    """Create stable graph node ids used in API graph payloads."""
    return f"{node_type}-{entity_id}"

# Map feedback DB rows to API schema objects.
def feedback_item_from_row(row: dict) -> RecommendationFeedbackItem:
    """Convert raw feedback SQL rows into API DTOs."""
    return RecommendationFeedbackItem(
        id=row["id"],
        sourceEntityType=row["source_entity_type"],
        sourceEntityId=row["source_entity_id"],
        candidateEntityType=row["candidate_entity_type"],
        candidateEntityId=row["candidate_entity_id"],
        feedback=row["feedback"],
        reason=row["reason"],
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )

# Validate that a referenced artist/event exists for feedback operations.
def ensure_feedback_entity_exists(
    connection: Connection,
    *,
    entity_type: EntityKind,
    entity_id: int,
) -> None:
    """Ensure referenced recommendation entity exists or raise 404."""
    table_name = "artists" if entity_type == "artist" else "events"
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT 1 FROM {table_name} WHERE id = %s", (entity_id,))
        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail=f"{entity_type} {entity_id} not found",
            )

# Load display metadata for recommendation entities.
def recommendation_item_metadata(
    connection: Connection,
    entity_type: EntityType,
    entity_ids: list[int],
) -> dict[int, dict]:
    """Load display metadata for recommendation candidates by entity type."""
    if not entity_ids:
        return {}

    if entity_type == "event":
        query = """
            SELECT
                e.id,
                e.ra_event_id,
                e.title AS name,
                e.event_date::date AS date,
                v.name AS venue_name,
                promoter.promoter_id,
                promoter.promoter_name
            FROM events e
            LEFT JOIN venues v
                ON v.id = e.venue_id
            LEFT JOIN LATERAL (
                SELECT
                    p.id AS promoter_id,
                    p.name AS promoter_name
                FROM event_promoters ep
                JOIN promoters p
                    ON p.id = ep.promoter_id
                WHERE ep.event_id = e.id
                ORDER BY p.id ASC
                LIMIT 1
            ) promoter
                ON true
            WHERE e.id = ANY(%s)
        """
    else:
        query = """
            SELECT
                id,
                NULL::text AS ra_event_id,
                name,
                NULL::date AS date,
                NULL::text AS venue_name,
                NULL::bigint AS promoter_id,
                NULL::text AS promoter_name
            FROM artists
            WHERE id = ANY(%s)
        """

    with connection.cursor() as cursor:
        cursor.execute(query, (entity_ids,))
        rows = cursor.fetchall()

    return {row["id"]: row for row in rows}

# Load artist semantic metadata (styles and extracted tags).
def artist_semantic_metadata(
    connection: Connection,
    artist_ids: list[int],
) -> dict[int, dict]:
    """Load artist semantic metadata (styles + extracted tags) for scoring."""
    if not artist_ids:
        return {}

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                name,
                COALESCE(biography_normalized, biography, '') AS biography
            FROM artists
            WHERE id = ANY(%s)
            """,
            (artist_ids,),
        )
        rows = cursor.fetchall()

        cursor.execute("SELECT to_regclass('public.artist_extracted_tags') AS table_name")
        has_extracted_tags = cursor.fetchone()["table_name"] is not None

        extracted_tags: dict[int, dict[str, list[str]]] = {}
        if has_extracted_tags:
            cursor.execute(
                """
                SELECT artist_id, tag_type, tag_value
                FROM artist_extracted_tags
                WHERE artist_id = ANY(%s)
                  AND confidence >= 0.6
                ORDER BY tag_type ASC, tag_value ASC
                """,
                (artist_ids,),
            )
            for tag in cursor.fetchall():
                artist_tags = extracted_tags.setdefault(tag["artist_id"], {})
                values = artist_tags.setdefault(tag["tag_type"], [])
                normalized = tag["tag_value"].strip()
                if normalized and normalized not in values:
                    values.append(normalized)

    metadata = {
        row["id"]: {
            "id": row["id"],
            "name": row["name"],
            "tags": extracted_tags.get(row["id"], {}),
            "style_tags": sorted(
                set(extract_style_tags(row["biography"]))
                | set(extracted_tags.get(row["id"], {}).get("style", []))
            ),
        }
        for row in rows
    }
    return metadata

# Compute capped overlap score between two tag lists.
def tag_overlap_score(source_tags: list[str], candidate_tags: list[str], cap: int = 1) -> float:
    """Compute case-insensitive overlap score with an upper cap."""
    if not source_tags or not candidate_tags:
        return 0.0

    overlap = {tag.casefold() for tag in source_tags} & {tag.casefold() for tag in candidate_tags}
    return min(len(overlap) / cap, 1.0)

# Return shared tag values with candidate-side canonical casing.
def shared_tag_values(source_tags: list[str], candidate_tags: list[str]) -> list[str]:
    """Return shared tag values preserving candidate-side canonical values."""
    candidate_lookup = {tag.casefold(): tag for tag in candidate_tags}
    return sorted(
        candidate_lookup[key]
        for key in ({tag.casefold() for tag in source_tags} & set(candidate_lookup.keys()))
    )

# Compute weighted score across extracted artist tag groups.
def extracted_tag_score(
    source_tags: dict[str, list[str]],
    candidate_tags: dict[str, list[str]],
    config: SemanticArtistTagScoringConfig,
) -> float:
    """Compute weighted overlap across extracted artist tag dimensions."""
    label_overlap = tag_overlap_score(source_tags.get("label", []), candidate_tags.get("label", []))
    collective_overlap = tag_overlap_score(
        source_tags.get("collective", []),
        candidate_tags.get("collective", []),
    )
    residency_overlap = tag_overlap_score(
        source_tags.get("residency", []),
        candidate_tags.get("residency", []),
    )
    role_overlap = tag_overlap_score(
        source_tags.get("role", []),
        candidate_tags.get("role", []),
        cap=config.role_overlap_cap,
    )

    return (
        config.label_weight * label_overlap
        + config.collective_weight * collective_overlap
        + config.residency_weight * residency_overlap
        + config.role_weight * role_overlap
    )

# Collect shared extracted tags grouped by tag type.
def shared_extracted_tags(
    source_tags: dict[str, list[str]],
    candidate_tags: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Collect shared extracted tags grouped by tag type for explanations."""
    shared: dict[str, list[str]] = {}
    for tag_type in ("label", "collective", "role", "residency", "alias"):
        values = shared_tag_values(source_tags.get(tag_type, []), candidate_tags.get(tag_type, []))
        if values:
            shared[tag_type] = values
    return shared

# Build and rank semantic artist candidates for recommendation flows.
def build_artist_semantic_candidates(
    connection: Connection,
    *,
    artist_id: int,
    debug: bool = False,
) -> tuple[dict, list[dict]]:
    """Rank semantic artist candidates using embeddings, style tags, and extracted tags."""
    config = EmbeddingConfig.from_env()
    scoring_config = semantic_artist_scoring_from_env()
    tag_scoring_config = semantic_artist_tag_scoring_from_env()
    source, ranked = rank_similar_embeddings(
        connection,
        entity_type="artist",
        entity_id=artist_id,
        config=config,
        limit=10_000,
    )

    if source is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No {config.model} embedding found for artist {artist_id}. "
                "Run scripts/generate_embeddings.py first."
            ),
        )

    candidate_ids = [item["entity_id"] for item in ranked]
    metadata = artist_semantic_metadata(connection, [artist_id, *candidate_ids])
    source_metadata = metadata.get(artist_id)
    if source_metadata is None:
        raise HTTPException(status_code=404, detail=f"Artist {artist_id} not found")

    source_tags = source_metadata["style_tags"]
    source_extracted_tags = source_metadata["tags"]
    scored = []
    for item in ranked:
        candidate_metadata = metadata.get(item["entity_id"])
        if candidate_metadata is None:
            continue

        candidate_tags = candidate_metadata["style_tags"]
        shared_styles = sorted(set(source_tags) & set(candidate_tags))
        style_score = style_overlap_score(source_tags, candidate_tags)
        tag_score = extracted_tag_score(
            source_extracted_tags,
            candidate_metadata["tags"],
            tag_scoring_config,
        )
        shared_tags = shared_extracted_tags(source_extracted_tags, candidate_metadata["tags"])
        embedding_score = item["score"]
        score_breakdown = {
            "embedding": scoring_config.embedding_weight * embedding_score,
            "style": scoring_config.style_weight * style_score,
            "tag": scoring_config.tag_weight * tag_score,
        }
        scored.append(
            {
                "entity_id": item["entity_id"],
                "name": candidate_metadata["name"],
                "score": sum(score_breakdown.values()),
                "embedding_score": embedding_score,
                "style_score": style_score,
                "tag_score": tag_score,
                "score_breakdown": score_breakdown,
                "shared_styles": shared_styles,
                "shared_tags": shared_tags,
                "debug": {
                    "sourceStyles": source_tags,
                    "candidateStyles": candidate_tags,
                    "sourceTags": source_extracted_tags,
                    "candidateTags": candidate_metadata["tags"],
                }
                if debug
                else None,
            }
        )

    return source, sorted(
        scored,
        key=lambda candidate: (-candidate["score"], candidate["entity_id"]),
    )
