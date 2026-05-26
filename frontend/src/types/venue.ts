import type { EventSummary } from './event'

export interface VenueDetail {
  type: 'venue'
  id: string
  name: string
  address?: string
  district?: string
  event_count: number
  events: EventSummary[]
}
