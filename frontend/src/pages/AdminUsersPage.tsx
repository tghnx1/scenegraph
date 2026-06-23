import { useEffect, useState } from 'react'
import { Button } from '@/shared/ui/button'
import { Badge } from '@/shared/ui/badge'
import {
  activateUser,
  approveUser,
  changeUserRole,
  deactivateUser,
  getPendingUsers,
  getUsers,
  rejectUser,
  type PendingUser,
  type UserItem,
} from '../api/auth'

interface AdminUsersPageProps {
  compact?: boolean
  onActivityChanged?: () => void | Promise<void>
}

export function AdminUsersPage({ compact = false, onActivityChanged }: AdminUsersPageProps) {
  const [users, setUsers] = useState<PendingUser[]>([])
  const [message, setMessage] = useState('')
  const [allUsers, setAllUsers] = useState<UserItem[]>([])

  const loadUsers = async () => {
    try {
      setUsers((await getPendingUsers()).users)
    } catch (error) {
      console.error(error)
      setMessage('Could not load pending users')
    }
  }

  const loadAllUsers = async () => {
    try {
      setAllUsers((await getUsers()).users)
    } catch (error) {
      console.error(error)
      setMessage('Could not load users')
    }
  }

  const refresh = async (nextMessage: string) => {
    setMessage(nextMessage)
    await Promise.all([loadUsers(), loadAllUsers(), onActivityChanged?.()])
  }

  useEffect(() => {
    void loadUsers()
    void loadAllUsers()
  }, [])

  const handleApprove = async (user: PendingUser) => {
    if (!confirm(`Approve ${user.username}?`)) return
    const response = await approveUser(user.id)
    await refresh(response.message)
  }

  const handleReject = async (user: PendingUser) => {
    if (!confirm(`Reject ${user.username}?`)) return
    const response = await rejectUser(user.id)
    await refresh(response.message)
  }

  const handleActivation = async (user: UserItem) => {
    const activating = user.status !== 'approved'
    if (!confirm(`${activating ? 'Activate' : 'Deactivate'} ${user.username}?`)) return
    const response = activating ? await activateUser(user.id) : await deactivateUser(user.id)
    await refresh(response.message)
  }

  const handleChangeRole = async (user: UserItem) => {
    const role = user.role === 'user' ? 'contributor' : 'user'
    const label = role === 'user' ? 'User' : 'Agent'
    if (!confirm(`Change ${user.username} to ${label}?`)) return
    const response = await changeUserRole(user.id, role)
    await refresh(response.message)
  }

  return (
    <section className="grid gap-3">
      {compact ? (
        <div className="flex items-center justify-between gap-3 border-b border-[var(--surface-border-soft)] pb-2 text-sm font-semibold text-[var(--text)]">
          <span>Pending user registrations</span>
        </div>
      ) : <h1 className="text-[32px]">Pending users</h1>}

      {message && <p className="text-sm text-[var(--text-muted)]">{message}</p>}
      <div className="grid max-h-32 gap-3 overflow-y-auto pr-1">
        {users.map((user) => (
          <div key={user.id} className="grid gap-2.5 rounded-xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-3">
            <div className="flex min-w-0 flex-wrap items-center gap-2 text-sm">
              <strong className="truncate">{user.username}</strong>
              <span className="truncate text-[var(--text-muted)]">{user.email}</span>
              <Badge variant="outline">{user.role}</Badge>
            </div>
            <div className="flex gap-2">
              <Button type="button" size="sm" onClick={() => handleApprove(user)}>Approve</Button>
              <Button type="button" size="sm" variant="destructive" onClick={() => handleReject(user)}>Reject</Button>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 border-b border-[var(--surface-border-soft)] pb-2 text-sm font-semibold">List of users</div>
      <div className="grid max-h-[300px] gap-3 overflow-y-auto pr-1">
        {allUsers.map((user) => (
          <div key={user.id} className="grid gap-2.5 rounded-xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-3">
            <div className="flex min-w-0 flex-wrap items-center gap-2 text-sm">
              <strong className="truncate">{user.username}</strong>
              <span className="truncate text-[var(--text-muted)]">{user.email}</span>
              <Badge variant="outline">{user.role}</Badge>
              <Badge variant="secondary">{user.status}</Badge>
            </div>
            {user.role !== 'admin' && ['approved', 'deactivated', 'rejected'].includes(user.status) && (
              <div className="flex flex-wrap gap-2">
                <Button type="button" size="sm" variant="outline" onClick={() => handleActivation(user)}>
                  {user.status === 'approved' ? 'Deactivate' : 'Activate'}
                </Button>
                {(user.role === 'user' || user.role === 'contributor') && (
                  <Button type="button" size="sm" variant="secondary" onClick={() => handleChangeRole(user)}>
                    Change to {user.role === 'user' ? 'Agent' : 'User'}
                  </Button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}
