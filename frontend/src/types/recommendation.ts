import type { GraphData } from './graph'

export interface PromoterRecommendation {
  id: number
  type: 'promoter'
  name: string
  score?: number
  baseScore?: number
  feedbackBoost?: number
  feedbackState?: 'positive' | 'negative' | null
  reasons: string[]
  warmConnectionArtists?: Array<{ id: number; name: string }>
  manualConnectionArtists?: Array<{ id: number; name: string }>
  promoterSizeSegment: 'small' | 'medium' | 'large'
  reasonDetails?: {
    similarPromoterEventTitles?: string[]
    sharedExtractedGenres?: string[]
    sharedExtractedGenreSources?: Record<string, Array<{
      eventId: number
      raEventId?: string | null
      title: string
      eventDate?: string | null
      sourceType: 'event_genres' | 'event_extracted_tags'
    }>>
    sharedThemes?: string[]
    sharedMoods?: string[]
    similarArtistNames?: string[]
    coPlayedArtistNames?: string[]
    manualArtistNames?: string[]
  }
  debug?: {
    weightedScores?: {
      total?: number
    }
    rawSignals?: {
      eventSimilarityEventTitles?: string[]
      sharedExtractedGenres?: string[]
      sharedThemes?: string[]
      sharedMoods?: string[]
      matchedArtistNames?: string[]
      coPlayedConnectionArtists?: Array<{ id: number; name: string }>
      manualConnectionArtists?: Array<{ id: number; name: string }>
    }
  }
}

export interface PromoterRecommendationResponse {
  entityId: number
  entityType: 'artist'
  recommendations: PromoterRecommendation[]
  graph: GraphData
  analyticsGraph?: GraphData | null
}

export type RecommendationJobStatus = 'queued' | 'running' | 'completed' | 'failed'

export interface RecommendationJobCreatedResponse {
  jobId: string
  status: RecommendationJobStatus
}

export interface RecommendationJobResponse {
  jobId: string
  jobType: 'artist_promoters'
  artistId: number
  params: {
    limit: number
    excludeExisting: boolean
    debug: boolean
  }
  status: RecommendationJobStatus
  result?: PromoterRecommendationResponse
  errorMessage?: string
  createdAt: string
  startedAt?: string
  finishedAt?: string
  updatedAt: string
}
