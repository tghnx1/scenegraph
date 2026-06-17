import {api} from './client'

export interface ManualArtistConnection {
  sourceArtistId: number
  connectedArtistId: number
  connectedArtistName: string
  createdAt: string
  updatedAt: string
}

export interface ManualArtistConnectionsResponse {
  items: ManualArtistConnection[]
}

export const listKnownArtists = (sourceArtistId: number) =>
  api.get<ManualArtistConnectionsResponse>(`/artists/${sourceArtistId}/known-artists`)

export const addKnownArtist = (sourceArtistId: number, connectedArtistId: number) =>
  api.post<ManualArtistConnection>(`/artists/${sourceArtistId}/known-artists`, {connectedArtistId})

export const removeKnownArtist = (sourceArtistId: number, connectedArtistId: number) =>
  api.delete<ManualArtistConnection>(`/artists/${sourceArtistId}/known-artists/${connectedArtistId}`)
