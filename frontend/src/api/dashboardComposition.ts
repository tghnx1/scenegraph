import {api} from './client'
import type {DashboardEntity, DashboardStatus} from '../types/dashboardComposition'

export type DashboardCompositionFilters = {
  entities: DashboardEntity[]
  dateFrom?: string
  dateTo?: string
}

export const fetchDashboardStatus = async ({
  entities,
  dateFrom,
  dateTo,
}: DashboardCompositionFilters): Promise<DashboardStatus> => {
  const params = new URLSearchParams({include: entities.join(',')})

  if (dateFrom) params.set('dateFrom', dateFrom)
  if (dateTo) params.set('dateTo', dateTo)

  return api.get<DashboardStatus>(`/admin/composition?${params.toString()}`)
}
