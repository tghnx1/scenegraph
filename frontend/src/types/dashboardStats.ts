export type DashboardMetricStatus = 'good' | 'warning' | 'critical' | 'neutral' | string

export interface DashboardMetric {
  id: string
  label: string
  value: number | string | null
  total: number | null
  percentage: number | null
  status: DashboardMetricStatus
  meaning: string
  whyItMatters: string
  fix: string | null
}

export interface DashboardRankingItem {
  id?: string | number
  name?: string
  label?: string
  value?: number | string | null
  count?: number | null
}

export interface DashboardRanking {
  id: string
  label: string
  items: DashboardRankingItem[]
  meaning: string
  whyItMatters: string
}

export interface DashboardStats {
  metrics: DashboardMetric[]
  rankings: DashboardRanking[]
  timestamps?: {
    latest_source_payload: string | null
  }
  latest_source_payload?: string | null
}
