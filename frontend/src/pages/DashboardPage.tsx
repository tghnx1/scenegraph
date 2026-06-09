import {fetchDashboardStatus} from '../api/status'
import {useApi} from '../hooks/useApi'

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

const managementActivityRows = [
  { actor: 'admin@scenegraph.local', event: 'Login', target: 'Admin console', time: '14:40' },
  { actor: 'maya@example.com', event: 'Claim request', target: 'Artist: CHO CORE', time: '14:18' },
  { actor: 'admin@scenegraph.local', event: 'Disabled claim', target: 'Promoter: SIGNALSBERLINEVENT', time: '13:52' },
  { actor: 'sam@example.com', event: 'Registration', target: 'User account', time: '12:27' },
  { actor: 'moderator.demo', event: 'Logout', target: 'Dashboard', time: '11:59' },
]

const claimRows = [
  { user: 'maya@example.com', node: 'Artist: CHO CORE', status: 'Pending review' },
  { user: 'artist.claim.demo', node: 'Promoter: Club Heart Broken', status: 'Needs proof' },
  { user: 'ronja@example.com', node: 'Artist: RONJA', status: 'Approved' },
]

function PanelHeading({ label, status }: { label: string; status: string }) {
  return (
    <div className="panel-heading">
      <span className="search-query-label">{label}</span>
      <span className="panel-status">{status}</span>
    </div>
  )
}

export function DashboardPage() {

  const {data: dashboardStatus, isLoading, error} = useApi(
  fetchDashboardStatus,
  []
)

  const overviewStats = [
  { label: 'Events', value: dashboardStatus?.events ?? '-', note: 'Total events' },
  { label: 'Artists', value: dashboardStatus?.artists ?? '-', note: 'Total artists' },
  { label: 'Venues', value: dashboardStatus?.venues ?? '-', note: 'Total venues' },
  { label: 'Promoters', value: dashboardStatus?.promoters ?? '-', note: 'Total promoters' },
  { label: 'Genres', value: dashboardStatus?.genres ?? '-', note: 'Total genres' },
	{ label: 'Artists without bio', value: dashboardStatus?.artists_no_bio ?? '-', note: 'Total artists without bio' },
  //{ label: 'Last import', value: '14:32', note: 'Resident Advisor' },
  ]

  return (
    <div className="dashboard-page">
      <div className="dashboard-actions" aria-label="Dashboard actions">
        <button type="button">Run import</button>
        <button type="button">View logs</button>
      </div>

      {error && <p className="error">Failed to load dashboard status.</p>}
      <section className="dashboard-overview" aria-label="SceneGraph overview">
        {overviewStats.map((item) => (
          <article key={item.label} className="dashboard-stat-card">
            <span>{item.label}</span>
            <strong>{isLoading ? '...' : error ? '-' : item.value?.toLocaleString() ?? '-'}</strong>
            <small>{item.note}</small>
          </article>
        ))}
      </section>

      <section className="dashboard-admin-grid" aria-label="Admin dashboard sections">
        <article className="dashboard-panel dashboard-status-element">
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

        <article className="dashboard-panel dashboard-status-element">
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

        <article className="dashboard-panel dashboard-panel-full dashboard-status-element">
          <div className="panel-heading">
            <span className="search-query-label">Management</span>
            <button type="button">Invite user</button>
          </div>
          <div className="dashboard-management-stack">
            <section>
              <div className="dashboard-section-heading">
                <span>Login, logout, and registration activity</span>
              </div>
              <div className="dashboard-table dashboard-table--management-log">
                {managementActivityRows.map((row) => (
                  <div key={`${row.actor}-${row.event}-${row.time}`} className="dashboard-table-row">
                    <strong>{row.actor}</strong>
                    <span>{row.event}</span>
                    <span>{row.target}</span>
                    <span>{row.time}</span>
                  </div>
                ))}
              </div>
            </section>
            <section>
              <div className="dashboard-section-heading">
                <span>Node claims</span>
              </div>
              <div className="dashboard-table dashboard-table--claims">
                {claimRows.map((row) => (
                  <div key={`${row.user}-${row.node}`} className="dashboard-table-row">
                    <strong>{row.user}</strong>
                    <span>{row.node}</span>
                    <span>{row.status}</span>
                    <button type="button">Review</button>
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
