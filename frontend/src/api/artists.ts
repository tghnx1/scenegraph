import { api } from './client'
import type { Artist } from '../types/artist'

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

export const fetchArtist = async (id: string, name?: string): Promise<Artist> => { //fetch one artist's full profile
  try {
    return await api.get<Artist>(`/artist?id=${encodeURIComponent(stripNodePrefix(id))}`) //calls GET /api/artist?id=<ra-artist-id>
  } catch (error) {
    if (!name || !isNotFound(error)) {
      throw error
    }

    const resolvedId = await resolveArtistIdByName(name)
    if (!resolvedId) {
      throw error
    }

    return api.get<Artist>(`/artist?id=${encodeURIComponent(stripNodePrefix(resolvedId))}`)
  }
}
