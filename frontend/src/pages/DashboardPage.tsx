import {useState} from 'react'
import {fetchDashboardStatus} from '../api/dashboardComposition'
import {fetchDashboardStats} from '../api/dashboardStats'
import {useApi} from '../api/useApi'
import type {DashboardEntity} from '../types/dashboardComposition'
import { Button } from '@/shared/ui/button'
import {DashboardExportMenu} from './components/ExportDashboard'
import {DashboardManagement} from './components/DashboardManagement'
import {DashboardMetricPanels} from './components/DashboardMetric'
import {DashboardStatistics} from './components/DashboardComposition'

export function DashboardPage() {
  const [selectedEntities, setSelectedEntities] = useState<DashboardEntity[]>([
    'events',
    'artists',
    'promoters',
    'venues',
  ])
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const include = selectedEntities.join(',')
  const {data: dashboardStatus, isLoading, error} = useApi(
    () => fetchDashboardStatus({entities: selectedEntities, dateFrom, dateTo}),
    [include, dateFrom, dateTo]
  )
  const {
    data: dashboardStats,
    isLoading: areStatsLoading,
    error: statsError,
  } = useApi(fetchDashboardStats, [])

  const toggleEntity = (entity: DashboardEntity) => {
    setSelectedEntities((current) => current.includes(entity)
      ? current.filter((item) => item !== entity)
      : [...current, entity]
    )
  }

  return (
    <div className="mx-auto min-h-full w-full max-w-[1480px] p-4">
      <div className="mb-4 flex justify-end gap-2" aria-label="Dashboard actions">
        <Button type="button">Run import</Button>
        <DashboardExportMenu
          dashboardStatus={dashboardStatus}
          selectedEntities={selectedEntities}
          dateFrom={dateFrom}
          dateTo={dateTo}
        />
      </div>

      {error && <p className="mt-5 text-[var(--event)]">Failed to load dashboard status.</p>}
      <section className="grid gap-5" aria-label="Admin dashboard sections">
        <DashboardStatistics
          dashboardStatus={dashboardStatus}
          isLoading={isLoading}
          hasError={Boolean(error)}
          selectedEntities={selectedEntities}
          onToggleEntity={toggleEntity}
          dateFrom={dateFrom}
          dateTo={dateTo}
          onDateRangeChange={(nextDateFrom, nextDateTo) => {
            setDateFrom(nextDateFrom)
            setDateTo(nextDateTo)
          }}
        />
        <DashboardMetricPanels
          dashboardStats={dashboardStats}
          isLoading={areStatsLoading}
          hasError={Boolean(statsError)}
        />
        <DashboardManagement />
      </section>
    </div>
  )
}
