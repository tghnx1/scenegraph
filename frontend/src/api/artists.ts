/* import { api } from './client'
import type { Artist, SimilarArtist } from '../types/artist'

export const fetchArtist = (id: string) =>
  api.get<Artist>(`/artists/${id}`)

export const fetchSimilarArtists = (id: string) =>
  api.get<SimilarArtist[]>(`/artists/${id}/similar`) */

import { MOCK_ARTISTS, MOCK_SIMILAR } from './mock'
import type { Artist, SimilarArtist } from '../types/artist'

export const fetchArtist = (id: string): Promise<Artist> => {
  // TODO: return api.get<Artist>(`/artists/${id}`)
  const artist = MOCK_ARTISTS[id]
  if (!artist) return Promise.reject(new Error(`Artist ${id} not found`))
  return Promise.resolve(artist)
}

export const fetchSimilarArtists = (id: string): Promise<SimilarArtist[]> => {
  // TODO: return api.get<SimilarArtist[]>(`/artists/${id}/similar`)
  return Promise.resolve(MOCK_SIMILAR[id] ?? [])
}