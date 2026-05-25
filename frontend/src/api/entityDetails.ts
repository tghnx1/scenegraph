import { api } from './client'
import { graphEntityId, type NodeType } from '../types/graph'
import type { EntityDetail } from '../types/entityDetail'

type DetailNodeType = Exclude<NodeType, 'artist'>

export const fetchEntityDetail = (type: DetailNodeType, id: string): Promise<EntityDetail> =>
  api.get<EntityDetail>(`/${type}?id=${encodeURIComponent(String(graphEntityId(id, type) ?? id))}`)
