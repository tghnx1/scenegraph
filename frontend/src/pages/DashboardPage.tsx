import {fetchDashboardStatus} from '../api/status'
import {useApi} from '../hooks/useApi'
import {DashboardManagement} from './components/DashboardManagement'
import {DashboardStatistics} from './components/DashboardStats'

export function DashboardPage() {
  const {data: dashboardStatus, isLoading, error} = useApi(
    fetchDashboardStatus,
    []
  )

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
        />
        <DashboardManagement />
      </section>
    </div>
  )
}
