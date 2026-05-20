const overviewStats = [
  { label: 'Events', value: '2,486', note: '+184 this import' },
  { label: 'Artists', value: '5,621', note: '438 newly linked' },
  { label: 'Venues', value: '312', note: '29 missing coordinates' },
  { label: 'Promoters', value: '1,048', note: '76 active this month' },
  { label: 'Genres', value: '18', note: 'Source tags' },
  { label: 'Last import', value: '14:32', note: 'Mocked status' },
]

const importRuns = [
  { source: 'Resident Advisor', status: 'Successful', processed: '1,250', changed: '184 new / 312 updated', finished: 'Today, 14:32' },
  { source: 'Artist biographies', status: 'Needs review', processed: '421', changed: '38 skipped', finished: 'Today, 11:08' },
  { source: 'Venue enrichment', status: 'Queued', processed: '-', changed: 'Waiting for worker', finished: 'Not started' },
]

const qualityItems = [
  { label: 'Events without artists', value: '42', tone: 'warning' },
  { label: 'Events without genres', value: '17', tone: 'good' },
  { label: 'Venues missing address', value: '29', tone: 'warning' },
  { label: 'Possible duplicate artists', value: '64', tone: 'danger' },
  { label: 'Isolated graph nodes', value: '118', tone: 'warning' },
]

const graphMetrics = [
  { label: 'Artist nodes', value: '5,621' },
  { label: 'Event nodes', value: '2,486' },
  { label: 'Venue nodes', value: '312' },
  { label: 'Promoter nodes', value: '1,048' },
  { label: 'Edges', value: '18,904' },
  { label: 'Avg. artist degree', value: '6.4' },
]

const entityRows = [
  { type: 'Event', name: 'SIGNALS with BabaBass3000', status: 'Visible', updated: '14:32' },
  { type: 'Artist', name: 'Charleen Herzig', status: 'Needs biography', updated: '13:41' },
  { type: 'Venue', name: 'Lokschuppen Berlin', status: 'Missing area note', updated: '12:09' },
  { type: 'Promoter', name: 'SIGNALSBERLINEVENT', status: 'Visible', updated: '11:56' },
]

const recommendationRows = [
  { artist: 'BabaBass3000', target: 'Lokschuppen Berlin', score: '92', reason: 'Shared techno events, recurring promoter' },
  { artist: 'Acidheaven', target: 'Arkaoda', score: '87', reason: 'House and trance overlap, recent lineup graph' },
  { artist: 'Flo Masse', target: 'Manolita', score: '81', reason: 'Promoter connection and similar event genres' },
]

const userRows = [
  { user: 'admin@scenegraph.local', role: 'Admin', status: 'Active' },
  { user: 'artist.claim.demo', role: 'Artist', status: 'Pending claim' },
  { user: 'moderator.demo', role: 'Moderator', status: 'Active' },
]

export function DashboardPage() {
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
        <article className="dashboard-panel dashboard-panel-wide dashboard-mock-element">
          <div className="panel-heading">
            <span className="search-query-label">Import monitor</span>
            <span className="panel-status">Mock data</span>
          </div>
          <div className="dashboard-table">
            {importRuns.map((run) => (
              <div key={run.source} className="dashboard-table-row">
                <strong>{run.source}</strong>
                <span>{run.status}</span>
                <span>{run.processed} processed</span>
                <span>{run.changed}</span>
                <span>{run.finished}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="dashboard-panel dashboard-mock-element">
          <div className="panel-heading">
            <span className="search-query-label">Data quality</span>
            <span className="panel-status">Review queue</span>
          </div>
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
          <div className="panel-heading">
            <span className="search-query-label">Graph health</span>
            <span className="panel-status">Current snapshot</span>
          </div>
          <div className="graph-health-grid">
            {graphMetrics.map((metric) => (
              <div key={metric.label}>
                <strong>{metric.value}</strong>
                <span>{metric.label}</span>
              </div>
            ))}
          </div>
          <div className="admin-graph-preview" aria-label="Graph health preview" />
        </article>

        <article className="dashboard-panel dashboard-panel-wide dashboard-mock-element">
          <div className="panel-heading">
            <span className="search-query-label">Entity browser</span>
            <button type="button">Search entities</button>
          </div>
          <div className="dashboard-table">
            {entityRows.map((row) => (
              <div key={`${row.type}-${row.name}`} className="dashboard-table-row">
                <strong>{row.type}</strong>
                <span>{row.name}</span>
                <span>{row.status}</span>
                <span>{row.updated}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="dashboard-panel dashboard-panel-wide dashboard-mock-element">
          <div className="panel-heading">
            <span className="search-query-label">Recommendation debug</span>
            <span className="panel-status">Explainability mock</span>
          </div>
          <div className="dashboard-table recommendation-table">
            {recommendationRows.map((row) => (
              <div key={`${row.artist}-${row.target}`} className="dashboard-table-row">
                <strong>{row.artist}</strong>
                <span>{row.target}</span>
                <span>{row.score}</span>
                <span>{row.reason}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="dashboard-panel dashboard-mock-element">
          <div className="panel-heading">
            <span className="search-query-label">Users and roles</span>
            <button type="button">Invite</button>
          </div>
          <div className="dashboard-table compact">
            {userRows.map((row) => (
              <div key={row.user} className="dashboard-table-row">
                <strong>{row.user}</strong>
                <span>{row.role}</span>
                <span>{row.status}</span>
              </div>
            ))}
          </div>
        </article>
      </section>
    </div>
  )
}
