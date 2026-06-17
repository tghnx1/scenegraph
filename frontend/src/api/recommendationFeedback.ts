import { api } from './client'

export type PromoterFeedbackValue = 'positive' | 'negative'

export interface PromoterFeedbackItem {
  id: number
  userId: number
  sourceEntityType: 'artist'
  sourceEntityId: number
  candidateEntityType: 'promoter'
  candidateEntityId: number
  feedback: PromoterFeedbackValue
  reason?: string | null
  createdAt: string
  updatedAt: string
}

interface PromoterFeedbackResponse {
  feedback: PromoterFeedbackItem[]
}

export const setPromoterFeedback = (
  artistId: number,
  promoterId: number,
  feedback: PromoterFeedbackValue,
): Promise<PromoterFeedbackItem> => api.post('/recommendation-feedback', {
  sourceEntityType: 'artist',
  sourceEntityId: artistId,
  candidateEntityType: 'promoter',
  candidateEntityId: promoterId,
  feedback,
})

export const getPromoterFeedback = (
  artistId: number,
  promoterId: number,
): Promise<PromoterFeedbackResponse> => api.get(
  `/recommendation-feedback?sourceEntityType=artist&sourceEntityId=${artistId}`
  + `&candidateEntityType=promoter&candidateEntityId=${promoterId}`,
)

export const deletePromoterFeedback = (feedbackId: number): Promise<PromoterFeedbackItem> =>
  api.delete(`/recommendation-feedback/${feedbackId}`)
