import type { GraphData } from './graph'

export interface PromoterRecommendation {
  id: number
  type: 'promoter'
  name: string
  reasons: string[]
  promoterSizeSegment: 'small' | 'medium' | 'large'
  reasonDetails?: {
    relatedEventTitles?: string[]
    similarPromoterEventTitles?: string[]
    similarArtistNames?: string[]
    coPlayedArtistNames?: string[]
    manualArtistNames?: string[]
  }
  debug?: {
    rawSignals?: {
      relatedEventTitles?: string[]
      eventSimilarityEventTitles?: string[]
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
}
