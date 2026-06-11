import { AdminUsersPage } from "./AdminUsersPage"
import { useEffect, useState } from 'react'
import { getActivityLog, type ActivityLogItem } from "../api/auth"

const overviewStats = [
  { label: 'Events', value: '2,486', note: '+184 this import' },
  { label: 'Artists', value: '5,621', note: '438 newly linked' },
  { label: 'Venues', value: '312', note: '18 recently updated' },
  { label: 'Promoters', value: '1,048', note: '76 active this month' },
  { label: 'Genres', value: '18', note: 'Imported taxonomy' },
  { label: 'Last import', value: '14:32', note: 'Resident Advisor' },
]

const qualityItems = [
  { label: 'Artists missing bio', value: '400', tone: 'warning' },
  { label: 'Venues missing address', value: '25', tone: 'warning' },
  { label: 'Events without venues', value: '9', tone: 'danger' },
  { label: 'Promoters without contact', value: '37', tone: 'warning' },
  { label: 'Possible duplicate artists', value: '64', tone: 'danger' },
  { label: 'Possible duplicate venues', value: '11', tone: 'warning' },
]

const dataStatistics = [
  { label: 'Avg artist connectivity', value: '6.4', note: 'connections per artist' },
  { label: 'Median artist connectivity', value: '3', note: 'typical artist degree' },
  { label: 'Avg promoter connectivity', value: '12.8', note: 'connections per promoter' },
  { label: 'Median promoter connectivity', value: '7', note: 'typical promoter degree' },
  { label: 'Incomplete networks', value: '118', note: 'missing artist, event, venue, or promoter' },
  { label: 'Complete networks', value: '1,932', note: 'all 4 entity types linked' },
]

export function DashboardPage() {
  const[activityRows, setActivityRows] = useState<ActivityLogItem[]>([])

  useEffect(() => {
    const loadActivity = async () => {
      try {
        const response = await getActivityLog()
        setActivityRows(response.activity)
      } catch (error) {
        console.error(error)
      }
    }
    loadActivity()
  }, [])

  return (
    <div className="dashboard-page">
      <div className="dashboard-actions" aria-label="Dashboard actions">
        <button type="button">Run import</button>
        <button type="button">View logs</button>
      </div>

      <section className="dashboard-overview" aria-label="SceneGraph overview">
        {overviewStats.map((item) => (
          <article key={item.label} className="dashboard-stat-card dashboard-mock-element">
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <small>{item.note}</small>
          </article>
        ))}
      </section>

      <section className="dashboard-admin-grid" aria-label="Admin dashboard sections">
        <article className="dashboard-panel dashboard-mock-element">
          <PanelHeading label="Data quality" status="Missing entries" />
          <div className="quality-list">
            {qualityItems.map((item) => (
              <div key={item.label} className={`quality-item ${item.tone}`}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
              </div>
            ))}
          </div>
        </article>

        <article className="dashboard-panel dashboard-mock-element">
          <PanelHeading label="Data statistics" status="Connectivity" />
          <div className="graph-health-grid">
            {dataStatistics.map((metric) => (
              <div key={metric.label}>
                <strong>{metric.value}</strong>
                <span>{metric.label}</span>
                <small>{metric.note}</small>
              </div>
            ))}
          </div>
        </article>

        <article className="dashboard-panel dashboard-panel-full dashboard-mock-element">
          <div className="panel-heading">
            <span className="search-query-label">Management</span>
            <button type="button">Invite user</button>
          </div>
          <div 
            className="dashboard-management-stack"
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: 24,
              alignItems: 'start',
            }}
          >
            <section>
              <AdminUsersPage compact />
            </section>

            <section>
              <div className="dashboard-section-heading">
                <span>Login, logout, and registration activity</span>
              </div>
              <div className="dashboard-table dashboard-table--management-log">
                {activityRows.map((row) => (
                  <div key={row.id} className="dashboard-table-row">
                    <strong>{row.username ?? 'unknown'}</strong>
                    <span>{row.event_type}</span>
                    <span>{row.target ?? '-'}</span>
                    <span>{new Date(row.created_at).toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </section>
           </div>
        </article>
      </section>
    </div>
  )
}
