import { useEffect, useState } from 'react'
import { Button } from '@/shared/ui/button'
import { approveUser, rejectUser, getPendingUsers, getUsers, deactivateUser, type PendingUser, type UserItem, } from '../api/auth'

interface AdminUsersPageProps { compact?: boolean }   //? means it's optional; compact is for a smaller version

export function AdminUsersPage({ compact = false }: AdminUsersPageProps) {
  const [users, setUsers] = useState<PendingUser[]>([])
  const [message, setMessage] = useState('')
  const [allUsers, setAllUsers] = useState<UserItem[]>([])

  //const loadUsers = async () => {
    //const response = await getPendingUsers()
    //setUsers(response.users)
  //}
  const loadUsers = async () => {
    try {
      const response = await getPendingUsers()
      setUsers(response.users)
    } catch (error) {
      console.error(error)
      setMessage('Could not load pending users')
    }
  }

  const loadAllUsers = async () => {
    try {
      const response = await getUsers()
      setAllUsers(response.users)
    } catch (error) {
      console.error(error)
      setMessage('Could not load users')
    }
  }

  useEffect(() => {
    loadUsers()
    loadAllUsers()
  }, [])

  const handleApprove = async (user: PendingUser) => {
    if (!confirm(`Approve ${user.username}?`)) return

    const response = await approveUser(user.id)
    setMessage(response.message)
    await loadUsers()
    await loadAllUsers()
  }

  const handleReject = async (user: PendingUser) => {
  if (!confirm(`Reject ${user.username}?`))
    return

    const response = await rejectUser(user.id)
    setMessage(response.message)
    await loadUsers()
    await loadAllUsers()
  }

  const handleDeactivate = async (user: UserItem) => {
    if (!confirm(`Deactivate ${user.username}?`)) return

    const response = await deactivateUser(user.id)
    setMessage(response.message)
    await loadUsers()
    await loadAllUsers()
  }

  return (
    <section className="grid gap-3">
      {compact ? (
        <div className="flex items-center justify-between gap-3 border-b border-[var(--surface-border-soft)] pb-2 text-sm font-semibold text-[var(--text)]">
          <span>Pending user registrations</span>
        </div>
      ) : (
        <h1 className="text-[32px]">Pending users</h1>
      )}

      {message && <p>{message}</p>}

      {users.map((user) => (
        <div 
          key={user.id}
          className="grid grid-cols-1 items-start gap-2.5 rounded-xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-3"
        >
          <div className="truncate whitespace-nowrap">
            <strong>{user.username}</strong>
            <span> — {user.email}</span>
          </div>

          <div className="flex gap-2">
            <Button type="button" size="sm" onClick={() => handleApprove(user)}>Approve</Button>
            <Button type="button" size="sm" variant="destructive" onClick={() => handleReject(user)}>Reject</Button>
          </div>
        </div>
      ))}

      <div className="mt-4 flex items-center justify-between gap-3 border-b border-[var(--surface-border-soft)] pb-2 text-sm font-semibold text-[var(--text)]">
        <span>List of users</span>
      </div>

      <div className="grid gap-3">
        {allUsers.map((user) => (
          <div
            key={user.id}
            className="grid grid-cols-1 gap-2.5 rounded-xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-3"
          >
            <div className="truncate whitespace-nowrap">
              <strong>{user.username}</strong>
              <span> — {user.email}</span>
              <span> — {user.status}</span>
            </div>

            {user.role !== 'admin' && user.status === 'approved' && (
              <div className="flex gap-2">
                <Button type="button" size="sm" variant="outline" onClick={() => handleDeactivate(user)}>
                  Deactivate
                </Button>
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}
