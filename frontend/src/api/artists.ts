import { api } from './client'
import type { Artist } from '../types/artist'
import { graphEntityId } from '../types/graph'

interface ArtistResponse {
  type: 'artist'
  id: number
  name: string
  genres: string[]
  bio: string | null
  event_count: number
  events: Array<{
    id: number
    title: string
    event_date: string | null
    venue_name: string | null
  }>
  connected_artists: Array<{
    id: number
    name: string
    shared_events: number
  }>
}

function internalArtistId(id: string): string {
  return String(graphEntityId(id, 'artist') ?? id)
}

export const fetchArtist = async (id: string): Promise<Artist> => {
  const artist = await api.get<ArtistResponse>(`/artist?id=${encodeURIComponent(internalArtistId(id))}`)

  return {
    type: artist.type,
    id: String(artist.id),
    name: artist.name,
    genres: artist.genres,
    bio: artist.bio,
    eventCount: artist.event_count,
    events: artist.events.map((event) => ({
      id: String(event.id),
      title: event.title,
      date: event.event_date,
      venue_name: event.venue_name,
    })),
    connectedArtists: artist.connected_artists.map((connectedArtist) => ({
      id: String(connectedArtist.id),
      name: connectedArtist.name,
      shared_events_count: connectedArtist.shared_events,
    })),
  }
}
