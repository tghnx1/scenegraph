const stats = [
  { label: 'Connected nodes', value: '0' },
  { label: 'Shared events', value: '0' },
  { label: 'Recommendations', value: '0' },
]

const legendItems = [
  { label: 'Artists', className: 'artist' },
  { label: 'Venues', className: 'venue' },
  { label: 'Events', className: 'event' },
]

export function DashboardPage() {
  return (
    <div className="dashboard-page">
      <section className="dashboard-grid" aria-label="Dashboard overview">
        <article className="dashboard-panel profile-panel">
          <div className="panel-heading">
            <span>Profile</span>
            <button type="button">Edit</button>
          </div>
          <h2>Artist biography</h2>
          <p>Self biography and claimed account fields appear here.</p>
          <div className="profile-fields">
            <span>Name</span>
            <span>Genres</span>
            <span>Location</span>
          </div>
        </article>

        <article className="dashboard-panel context-panel">
          <div className="panel-heading">
            <span>Context</span>
            <span className="panel-status">Node details</span>
          </div>
          <h2>Selection details</h2>
          <p>Selected node information, definitive search results, and related entities.</p>
        </article>

        <article className="dashboard-panel side-panel recommendations-panel">
          <div className="panel-heading">
            <span>Recommendations</span>
            <span className="panel-status">Draft</span>
          </div>
          <div className="placeholder-list">
            <span>Recommended names</span>
            <span>A list of names/connections.</span>
          </div>
        </article>

        <article className="dashboard-panel stats-panel">
          <div className="panel-heading">
            <span>Statistics</span>
            <span className="panel-status">Overview</span>
          </div>
          <div className="stat-grid">
            {stats.map((item) => (
              <div key={item.label} className="stat-tile">
                <strong>{item.value}</strong>
                <span>{item.label}</span>
              </div>
            ))}
          </div>
          <div className="chart-placeholder" aria-label="Chart placeholder" />
        </article>

        <section className="graph-workspace" aria-label="Dashboard graph workspace">
          <div className="dashboard-search-strip">
            <strong>Search input field</strong>
            <span>Selectable dropdown results</span>
          </div>

          <article className="dashboard-panel graph-panel">
            <div className="panel-heading">
              <span>Graph display</span>
              <div className="graph-panel-actions">
                <button type="button">Filter by date</button>
                <button type="button">Filter by limit</button>
              </div>
            </div>
            <div className="dashboard-graph-placeholder" />
            <div className="legend-bar">
              <strong>Legends bar</strong>
              <div>
                {legendItems.map((item) => (
                  <span key={item.label} className={`legend-dot ${item.className}`}>
                    {item.label}
                  </span>
                ))}
              </div>
            </div>
          </article>
        </section>

        <article className="dashboard-panel side-panel communications-panel">
          <div className="panel-heading">
            <span>Communications</span>
            <span className="panel-status">Inbox</span>
          </div>
          <div className="placeholder-list">
            <span>Clickable contact names</span>
            <span>Open a chat</span>
          </div>
        </article>

        <article className="dashboard-panel empty-panel" aria-label="Empty dashboard panel" />
      </section>
    </div>
  )
}
