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

export function DashboardManagement() {
  return (
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
  )
}
