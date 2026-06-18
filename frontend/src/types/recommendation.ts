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
