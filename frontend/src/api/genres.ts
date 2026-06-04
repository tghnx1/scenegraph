import { api } from './client'

export interface GenreOption {
  name: string
  value: string
}

interface GenresResponse {
  genres: GenreOption[]
}

export const fetchGenres = async (): Promise<GenreOption[]> => {
  const response = await api.get<GenresResponse>('/genres')
  return response.genres
}
