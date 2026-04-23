/* import { api } from './client'
import type { Artist, SimilarArtist } from '../types/artist'

export const fetchArtist = (id: string) => //fetch one artist's full profile -> used on /artist/:id page
  api.get<Artist>(`/artists/${id}`) //calls GET /api/artists/<id> -> Vite proxy -> db's GET /artists/:id

export const fetchSimilarArtists = (id: string) =>
  api.get<SimilarArtist[]>(`/artists/${id}/similar`) //returns an [], not a single object
*/

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