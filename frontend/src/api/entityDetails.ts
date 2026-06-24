import { api } from './client'
import { graphEntityId, type NodeType } from '../types/graph'
import type { EntityDetail } from '../types/entityDetail'
import type { ArtistDetail } from '../types/artist'

const detailPathByType: Record<NodeType, string> = {
  artist: 'artist',
  event: 'event',
  venue: 'venue',
  promoter: 'promoter',
}

export const fetchEntityDetail = (type: NodeType, id: string): Promise<EntityDetail> => {
  const entityId = graphEntityId(id, type) ?? id

  return api.get<EntityDetail>(
    `/${detailPathByType[type]}/${encodeURIComponent(String(entityId))}`
  )
}

export interface ArtistBiographyResponse {
  id: number
  name: string
  biography: string
}

export const fetchArtistBiography = (artistId: number): Promise<ArtistDetail> =>
  api.get<ArtistDetail>(`/artist/${artistId}`)

export const updateArtistBiography = (
  artistId: number,
  biography: string,
): Promise<ArtistBiographyResponse> =>
  api.patch<ArtistBiographyResponse>(`/artist/${artistId}/biography`, {biography})

export const claimArtistProfile = (
  artistId: number,
  reason: string,
): Promise<{ success: boolean; message: string; claim_id: number }> =>
  api.post(`/artists/${artistId}/claim`, { reason })
