import {api} from './client'
import type {DashboardMetrics} from '../types/dashboardMetrics'

export const fetchDashboardMetrics = async (): Promise<DashboardMetrics> => {
  return api.get<DashboardMetrics>('/admin/metrics')
}
