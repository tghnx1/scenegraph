import {api} from './client'
import type {DashboardStatus} from '../types/status'

export const fetchDashboardStatus = async (): Promise<DashboardStatus> => {
  return api.get<DashboardStatus>('/dashboard/status/')
}