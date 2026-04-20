import { api } from './client'
import type { Artist, SimilarArtist } from '../types/artist'

export const fetchArtist = (id: string) =>
  api.get<Artist>(`/artists/${id}`)

export const fetchSimilarArtists = (id: string) =>
  api.get<SimilarArtist[]>(`/artists/${id}/similar`)