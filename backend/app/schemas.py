from __future__ import annotations

from datetime import date as DateValue
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Venue(BaseModel):
    id: int
    name: str
    district: str
    scene_focus: str


class VenuesResponse(BaseModel):
    venues: list[Venue]


class GraphNode(BaseModel):
    id: str
    entityId: int
    type: Literal["artist", "event", "venue", "promoter"]
    name: str
    genres: list[str] = Field(default_factory=list)
    eventCount: int | None = None
    date: DateValue | None = None
    startDate: DateValue | None = None
    endDate: DateValue | None = None
    district: str | None = None
    sceneFocus: str | None = None


class GraphLink(BaseModel):
    source: str
    target: str
    relationship: str
    weight: int = 1
    evidenceType: str | None = None
    style: Literal["solid", "dashed"] | None = None
    strength: float | None = None


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    links: list[GraphLink]
    graphMode: Literal["compact", "full"] | None = None
    preferredPathNodeIds: dict[str, list[str]] = Field(default_factory=dict)
    preferredPathLinkKeys: dict[str, list[str]] = Field(default_factory=dict)
    preferredPathPromoterIdsByNodeId: dict[str, list[str]] = Field(default_factory=dict)
    preferredPathPromoterIdsByLinkKey: dict[str, list[str]] = Field(default_factory=dict)
    fallbackPathNodeIds: dict[str, list[str]] = Field(default_factory=dict)
    fallbackPathLinkKeys: dict[str, list[str]] = Field(default_factory=dict)
    fallbackPathPromoterIdsByNodeId: dict[str, list[str]] = Field(default_factory=dict)
    fallbackPathPromoterIdsByLinkKey: dict[str, list[str]] = Field(default_factory=dict)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str
    user_id: int | None = None
    username: str | None = None
    role: str | None = None
    artist_id: int | None = None
    access_token: str | None = None
    must_change_password: bool | None = None


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    password_confirm: str
    role: Literal["artist", "agent", "admin"]
    artist_id: int | None = None

class RegisterResponse(BaseModel):
    success: bool
    message: str
    user_id: int | None = None

class ChangePasswordRequest(BaseModel):
    username: str
    current_password: str
    new_password: str
    new_password_confirm: str

class ChangePasswordResponse(BaseModel):
    success: bool
    message: str

class ChangeRoleRequest(BaseModel):
    role: Literal["artist", "agent"]


class SimilarityItem(BaseModel):
    id: int
    type: Literal["artist", "event"]
    name: str
    score: float
    semanticScore: float
    graphScore: float
    scoreBreakdown: dict[str, float] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    date: DateValue | None = None
    venueName: str | None = None
    promoterId: int | None = None
    promoterName: str | None = None
    debug: dict[str, object] | None = None


class SimilarityResponse(BaseModel):
    entityId: int
    entityType: Literal["artist", "event"]
    model: str
    dimensions: int
    similar: list[SimilarityItem]
    debug: dict[str, object] | None = None


class SemanticArtistItem(BaseModel):
    id: int
    type: Literal["artist"] = "artist"
    name: str
    score: float
    embeddingScore: float
    styleScore: float
    tagScore: float = 0.0
    scoreBreakdown: dict[str, float] = Field(default_factory=dict)
    sharedStyles: list[str] = Field(default_factory=list)
    sharedTags: dict[str, list[str]] = Field(default_factory=dict)
    debug: dict[str, object] | None = None


class SemanticArtistResponse(BaseModel):
    entityId: int
    entityType: Literal["artist"] = "artist"
    model: str
    dimensions: int
    similar: list[SemanticArtistItem]


class RecommendationEvidenceItem(BaseModel):
    type: Literal["semantic_bridge", "warm_network", "manual_connection", "event_similarity"]
    path: str


class PromoterGenreSourceItem(BaseModel):
    eventId: int
    raEventId: str | None = None
    title: str
    eventDate: DateValue | None = None
    sourceType: Literal["event_genres", "event_extracted_tags"]


class WarmConnectionArtistItem(BaseModel):
    id: int
    name: str


class PromoterRecommendationReasonDetails(BaseModel):
    similarPromoterEventTitles: list[str] = Field(default_factory=list)
    sharedExtractedGenres: list[str] = Field(default_factory=list)
    sharedExtractedGenreSources: dict[str, list[PromoterGenreSourceItem]] = Field(default_factory=dict)
    sharedThemes: list[str] = Field(default_factory=list)
    sharedMoods: list[str] = Field(default_factory=list)
    similarArtistNames: list[str] = Field(default_factory=list)
    coPlayedArtistNames: list[str] = Field(default_factory=list)
    manualArtistNames: list[str] = Field(default_factory=list)


class PromoterRecommendationItem(BaseModel):
    id: int
    type: Literal["promoter"] = "promoter"
    name: str
    score: float
    baseScore: float | None = None
    feedbackBoost: float = 0.0
    feedbackState: Literal["positive", "negative"] | None = None
    semanticScore: float
    strengthScore: float
    activityScore: float
    recencyScore: float
    scoreBreakdown: dict[str, float] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    matchedArtistCount: int
    eventCount: int
    latestEventDate: DateValue | None = None
    status: str | None = None
    warmConnectionCount: int = 0
    warmConnectionArtists: list[WarmConnectionArtistItem] = Field(default_factory=list)
    coPlayedConnectionCount: int = 0
    coPlayedConnectionArtists: list[WarmConnectionArtistItem] = Field(default_factory=list)
    manualConnectionCount: int = 0
    manualConnectionArtists: list[WarmConnectionArtistItem] = Field(default_factory=list)
    promoterInterestedSum: int = 0
    promoterSizeSegment: Literal["small", "medium", "large"] = "small"
    evidence: list[RecommendationEvidenceItem] = Field(default_factory=list)
    reasonDetails: PromoterRecommendationReasonDetails = Field(
        default_factory=PromoterRecommendationReasonDetails
    )
    debug: dict[str, object] | None = None


class PromoterRecommendationResponse(BaseModel):
    entityId: int
    entityType: Literal["artist"] = "artist"
    model: str
    dimensions: int
    recommendations: list[PromoterRecommendationItem]
    largeRecommendations: list[PromoterRecommendationItem] = Field(default_factory=list)
    mediumRecommendations: list[PromoterRecommendationItem] = Field(default_factory=list)
    smallRecommendations: list[PromoterRecommendationItem] = Field(default_factory=list)
    warmRecommendations: list[PromoterRecommendationItem] = Field(default_factory=list)
    discoveryRecommendations: list[PromoterRecommendationItem] = Field(default_factory=list)
    graph: GraphResponse
    analyticsGraph: GraphResponse | None = None
    debug: dict[str, object] | None = None


RecommendationJobStatus = Literal["queued", "running", "completed", "failed"]


class RecommendationJobParams(BaseModel):
    limit: int = Field(default=50, ge=1)
    debug: bool = False


class RecommendationJobCreatedResponse(BaseModel):
    jobId: str
    status: RecommendationJobStatus


class RecommendationJobResponse(BaseModel):
    jobId: str
    jobType: Literal["artist_promoters"]
    artistId: int
    params: RecommendationJobParams
    status: RecommendationJobStatus
    result: PromoterRecommendationResponse | None = None
    errorMessage: str | None = None
    createdAt: datetime
    startedAt: datetime | None = None
    finishedAt: datetime | None = None
    updatedAt: datetime


class ArtistTagItem(BaseModel):
    type: Literal["style", "label", "collective", "role", "residency", "alias"]
    value: str
    source: str
    confidence: float
    extractor: str
    evidence: str | None = None


class ArtistTagsResponse(BaseModel):
    artistId: int
    artistName: str
    tags: list[ArtistTagItem]


FeedbackSourceKind = Literal["artist"]
FeedbackCandidateKind = Literal["promoter"]
FeedbackValue = Literal["positive", "negative"]


class RecommendationFeedbackRequest(BaseModel):
    sourceEntityType: FeedbackSourceKind
    sourceEntityId: int
    candidateEntityType: FeedbackCandidateKind
    candidateEntityId: int
    feedback: FeedbackValue
    reason: str | None = None


class RecommendationFeedbackItem(BaseModel):
    id: int
    userId: int
    sourceEntityType: FeedbackSourceKind
    sourceEntityId: int
    candidateEntityType: FeedbackCandidateKind
    candidateEntityId: int
    feedback: FeedbackValue
    reason: str | None = None
    createdAt: datetime
    updatedAt: datetime


class RecommendationFeedbackResponse(BaseModel):
    feedback: list[RecommendationFeedbackItem]


class ArtistKnownConnectionRequest(BaseModel):
    connectedArtistId: int


class ArtistKnownConnectionItem(BaseModel):
    sourceArtistId: int
    connectedArtistId: int
    connectedArtistName: str
    createdAt: datetime
    updatedAt: datetime


class ArtistKnownConnectionResponse(BaseModel):
    items: list[ArtistKnownConnectionItem]
