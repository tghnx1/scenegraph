import { api } from './client'
import { graphEntityId, type NodeType } from '../types/graph'
import type { EntityDetail } from '../types/entityDetail'

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