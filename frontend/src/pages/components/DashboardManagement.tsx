import { Button } from '@/shared/ui/button'

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
    <article className="rounded-3xl border border-[color-mix(in_srgb,var(--text)_10%,transparent)] bg-[color-mix(in_srgb,var(--background)_42%,transparent)] p-5 shadow-[0_10px_24px_rgba(0,0,0,0.12)] backdrop-blur-sm">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">Management</span>
        <Button type="button" size="sm">Invite user</Button>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-4 max-[900px]:grid-cols-1">
        <section>
          <div className="flex items-center justify-between gap-3 border-b border-[var(--surface-border-soft)] pb-2 text-sm font-semibold text-[var(--text)]">
            <span>Login, logout, and registration activity</span>
          </div>
          <div className="mt-3 grid gap-2">
            {managementActivityRows.map((row) => (
              <div key={`${row.actor}-${row.event}-${row.time}`} className="grid grid-cols-[1.2fr_0.8fr_1fr_auto] items-center gap-3 rounded-xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-3 text-sm max-[900px]:grid-cols-1">
                <strong>{row.actor}</strong>
                <span>{row.event}</span>
                <span>{row.target}</span>
                <span>{row.time}</span>
              </div>
            ))}
          </div>
        </section>
        <section>
          <div className="flex items-center justify-between gap-3 border-b border-[var(--surface-border-soft)] pb-2 text-sm font-semibold text-[var(--text)]">
            <span>Node claims</span>
          </div>
          <div className="mt-3 grid gap-2">
            {claimRows.map((row) => (
              <div key={`${row.user}-${row.node}`} className="grid grid-cols-[1fr_1fr_auto_auto] items-center gap-3 rounded-xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-3 text-sm max-[900px]:grid-cols-1">
                <strong>{row.user}</strong>
                <span>{row.node}</span>
                <span>{row.status}</span>
                <Button type="button" size="sm" variant="outline">Review</Button>
              </div>
            ))}
          </div>
        </section>
      </div>
    </article>
  )
}
