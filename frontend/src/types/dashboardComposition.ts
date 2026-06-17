export type DashboardEntity = 'events' | 'artists' | 'promoters' | 'venues'

export interface DashboardCompositionItem {
  id: DashboardEntity
  label: string
  value: number
  percentage: number
}

export interface DashboardStatus {
  from: string | null
  to: string | null
  total: number
  items: DashboardCompositionItem[]
}
