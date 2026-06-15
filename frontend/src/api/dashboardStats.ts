import {api} from './client'
import type {DashboardStats} from '../types/dashboardStats'

export const fetchDashboardStats = async (): Promise<DashboardStats> => {
  return api.get<DashboardStats>('/admin/stats')
}
