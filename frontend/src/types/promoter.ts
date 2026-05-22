import type { EventSummary } from './event'

export interface PromoterDetail {
  type: 'promoter'
  id: string
  name: string
  eventCount: number
  events: EventSummary[]
}
