import type { EventSummary } from './event'

export interface PromoterDetail {
  type: 'promoter'
  id: string
  name: string
  event_count: number
  events: EventSummary[]
}
