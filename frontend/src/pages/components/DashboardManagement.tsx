import { useCallback, useEffect, useState } from 'react'
import { Button } from '@/shared/ui/button'
import { exportActivityLog, getActivityLog, type ActivityLogItem } from '../../api/auth'
import { AdminUsersPage } from '../AdminUsersPage'

export function DashboardManagement() {
  const [activityRows, setActivityRows] = useState<ActivityLogItem[]>([])

  const loadActivity = useCallback(async () => {
    try {
      setActivityRows((await getActivityLog()).activity)
    } catch (error) {
      console.error(error)
    }
  }, [])

  useEffect(() => {
    void loadActivity()
  }, [loadActivity])

  return (
    <article className="rounded-3xl border border-[color-mix(in_srgb,var(--text)_10%,transparent)] bg-[color-mix(in_srgb,var(--background)_42%,transparent)] p-5 shadow-[0_10px_24px_rgba(0,0,0,0.12)] backdrop-blur-sm">
      <div className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">Management</div>
      <div className="mt-4 grid grid-cols-2 items-start gap-4 max-[900px]:grid-cols-1">
        <AdminUsersPage compact onActivityChanged={loadActivity} />
        <section>
          <div className="flex items-center justify-between gap-3 border-b border-[var(--surface-border-soft)] pb-2 text-sm font-semibold">
            <span>Login, logout, and registration activity</span>
            <Button type="button" size="sm" variant="outline" onClick={() => void exportActivityLog()}>Export</Button>
          </div>
          <div className="mt-3 grid max-h-[460px] gap-2 overflow-y-auto pr-1 font-mono text-xs">
            {activityRows.map((row) => (
              <div key={row.id} className="grid grid-cols-[170px_120px_1fr] gap-3 border-b border-[var(--surface-border-soft)] py-2 max-[1100px]:grid-cols-1">
                <span>{new Date(row.created_at).toLocaleString()}</span>
                <strong>{row.event_type}</strong>
                <span>{row.username ?? 'unknown'} -&gt; {row.target ?? '-'}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </article>
  )
}
