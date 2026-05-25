export interface ArtistEventItem {
  id: string
  title: string
  date: string | null
  venue_name: string | null
}

export interface ConnectedArtistItem {
  id: string
  name: string
  shared_events_count: number
}

export interface Artist {
  type: 'artist'
  id: string
  name: string
  genres: string[]
  bio: string | null
  eventCount: number
  events: ArtistEventItem[]
  connectedArtists: ConnectedArtistItem[]
}
