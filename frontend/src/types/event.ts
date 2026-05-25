export interface EntityReference {
  id: string
  name: string
}

export interface EventSummary {
  id: string
  title: string
  date: string | null
  venue_name?: string | null
  artists: string[]
  promoters: string[]
}

export interface EventDetail {
  type: 'event'
  id: string
  title: string
  date: string | null
  venue: EntityReference | null
  artists: EntityReference[]
  promoters: EntityReference[]
}
