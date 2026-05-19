import { api } from './client'
import type { Artist, SimilarArtist } from '../types/artist'

export const fetchArtist = (id: string) => //fetch one artist's full profile
  api.get<Artist>(`/artist?id=${encodeURIComponent(id)}`) //calls GET /api/artist?id=<artist-node-id>

export const fetchSimilarArtists = (_id: string) =>
  Promise.resolve([] as SimilarArtist[]) //rich artist detail includes connectedArtists; keep signature for callers

// import { MOCK_ARTISTS, MOCK_SIMILAR } from './mock_data/mock'

// export const fetchArtist = (id: string): Promise<Artist> => {
//   const artist = MOCK_ARTISTS[id]
//   if (!artist) return Promise.reject(new Error(`Artist ${id} not found`))
//   return Promise.resolve(artist)
// }

// export const fetchSimilarArtists = (id: string): Promise<SimilarArtist[]> => {
//   return Promise.resolve(MOCK_SIMILAR[id] ?? [])
// }
