import {useState} from 'react'
import {fetchDashboardStatus} from '../api/dashboardComposition'
import {useApi} from '../hooks/useApi'
import type {DashboardEntity} from '../types/dashboardComposition'
import {DashboardManagement} from './components/DashboardManagement'
import {DashboardStatistics} from './components/DashboardStats'

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

  const toggleEntity = (entity: DashboardEntity) => {
    setSelectedEntities((current) => current.includes(entity)
      ? current.filter((item) => item !== entity)
      : [...current, entity]
    )
  }

  return (
    <div className="dashboard-page">
      <div className="dashboard-actions" aria-label="Dashboard actions">
        <button type="button">Run import</button>
        <button type="button">View logs</button>
      </div>

      {error && <p className="error">Failed to load dashboard status.</p>}
      <section className="dashboard-admin-grid" aria-label="Admin dashboard sections">
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
        <DashboardManagement />
      </section>
    </div>
  )
}
