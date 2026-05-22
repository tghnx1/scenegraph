export interface EntityReference {
  id: string
  name: string
}

export interface EventSummary {
  id: string
  title: string
  date: string
  venue_name: string
  artists: string[]
  promoters: string[]
}

export interface EventDetail {
  type: 'event'
  id: string
  title: string
  date: string
  venue: EntityReference
  artists: EntityReference[]
  promoters: EntityReference[]
}
