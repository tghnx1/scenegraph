import type { GraphData } from './graph'

export interface PromoterRecommendation {
  id: number
  type: 'promoter'
  name: string
  reasons: string[]
}

export interface PromoterRecommendationResponse {
  entityId: number
  entityType: 'artist'
  recommendations: PromoterRecommendation[]
  graph: GraphData
}
