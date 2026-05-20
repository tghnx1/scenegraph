import { api } from './client'
import type { Artist, SimilarArtist } from '../types/artist'
import type { SearchArtistConnection, SearchEventSummary } from '../types/search'

interface ArtistEventApiItem {
  id: string
  title: string
  date: string
  venue_name: string
}

interface ConnectedArtistApiItem {
  id: string
  name: string
  shared_events_count: number
}

interface ArtistApiResponse extends Omit<Artist, 'events' | 'connectedArtists'> {
  events?: ArtistEventApiItem[]
  connectedArtists?: ConnectedArtistApiItem[]
}

const stripNodePrefix = (id: string) => id.replace(/^artist-/, '')
const isNotFound = (error: unknown) => error instanceof Error && error.message.startsWith('404 ')

async function resolveArtistIdByName(name: string): Promise<string | null> {
  const response = await api.get<{ results: Array<{ type: string, id: string, name: string }> }>(
    `/search?q=${encodeURIComponent(name)}&limit=10`
  )
  const match = response.results.find((result) => (
    result.type === 'artist' && result.name.toLowerCase() === name.toLowerCase()
  ))

  return match?.id ?? null
}

const toEventSummary = (event: ArtistEventApiItem): SearchEventSummary => ({
  id: event.id,
  label: event.title,
  date: event.date,
  venueName: event.venue_name,
  artists: [],
  promoters: [],
})

const toArtistConnection = (artist: ConnectedArtistApiItem): SearchArtistConnection => ({
  id: artist.id,
  label: artist.name,
  sharedEvents: artist.shared_events_count,
})

export const fetchArtist = async (id: string, name?: string): Promise<Artist> => { //fetch one artist's full profile
  let response: ArtistApiResponse

  try {
    response = await api.get<ArtistApiResponse>(`/artist?id=${encodeURIComponent(stripNodePrefix(id))}`) //calls GET /api/artist?id=<ra-artist-id>
  } catch (error) {
    if (!name || !isNotFound(error)) {
      throw error
    }

    const resolvedId = await resolveArtistIdByName(name)
    if (!resolvedId) {
      throw error
    }

    response = await api.get<ArtistApiResponse>(`/artist?id=${encodeURIComponent(stripNodePrefix(resolvedId))}`)
  }

  return {
    ...response,
    events: response.events?.map(toEventSummary) ?? [],
    connectedArtists: response.connectedArtists?.map(toArtistConnection) ?? [],
  }
}

export const fetchSimilarArtists = (_id: string) =>
  Promise.resolve([] as SimilarArtist[]) //rich artist detail includes connectedArtists; keep signature for callers
