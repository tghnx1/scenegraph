export interface ArtistEventItem {
  id: number
  title: string
  event_date: string | null
  venue_name: string | null
}

export interface ConnectedArtistItem {
  id: number
  name: string
  shared_events: number
}

export interface ArtistDetail {
  type: 'artist'
  id: number
  name: string
  genres: string[]
  bio: string | null
  event_count: number
  events: ArtistEventItem[]
  connected_artists: ConnectedArtistItem[]
}
