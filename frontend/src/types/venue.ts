import type { EventSummary } from './event'

export interface VenueDetail {
  type: 'venue'
  id: string
  name: string
  address?: string
  district?: string
  eventCount: number
  events: EventSummary[]
}
