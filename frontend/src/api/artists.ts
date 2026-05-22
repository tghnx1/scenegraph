import { api } from './client'
import type { Artist } from '../types/artist'
import { graphEntityId } from '../types/graph'

function internalArtistId(id: string): string {
  return String(graphEntityId(id, 'artist') ?? id)
}

export const fetchArtist = (id: string): Promise<Artist> =>
  api.get<Artist>(`/artist?id=${encodeURIComponent(internalArtistId(id))}`)
