import { useEffect, useState } from 'react'
import { changeUserRole, approveUser, rejectUser, getPendingUsers, getUsers, deactivateUser, activateUser, type PendingUser, type UserItem, } from '../api/auth'

interface AdminUsersPageProps { 
  compact?: boolean
  onActivityChanged?: () => Promise<void>       //to update directly the log, the child adminuserpage has to ask the dashboardpage.
}  

export function AdminUsersPage({ compact = false, onActivityChanged, }: AdminUsersPageProps) {
  const [users, setUsers] = useState<PendingUser[]>([])
  const [message, setMessage] = useState('')
  const [allUsers, setAllUsers] = useState<UserItem[]>([])

  const adminButtonStyle = {
    width: '140px',
  }

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
    //setMessage(response.message)
    await loadUsers()
    await loadAllUsers()
    await onActivityChanged?.()
  }

  const handleReject = async (user: PendingUser) => {
  if (!confirm(`Reject ${user.username}?`))
    return

    const response = await rejectUser(user.id)
    //setMessage(response.message)
    await loadUsers()
    await loadAllUsers()
    await onActivityChanged?.()
  }

  const handleDeactivate = async (user: UserItem) => {
    if (!confirm(`Deactivate ${user.username}?`)) return

    const response = await deactivateUser(user.id)
    //setMessage(response.message)
    await loadUsers()
    await loadAllUsers()
    await onActivityChanged?.()
  }

  const handleActivate = async (user: UserItem) => {
    if (!confirm(`Activate ${user.username}?`)) return

    const response = await activateUser(user.id)
    //setMessage(response.message)
    await loadUsers()
    await loadAllUsers()
    await onActivityChanged?.()
  }

  const handleChangeRole = async (user: UserItem) => {
    const newRole = user.role === 'artist' ? 'agent' : 'artist'

    if (!confirm(`Change ${user.username} to ${newRole}?`)) return

    const response = await changeUserRole(user.id, newRole)
    //setMessage(response.message)
    await loadUsers()
    await loadAllUsers()
    await onActivityChanged?.()
  }

  return (
    <section style={{ display: 'grid', gap: 12}}>
      {compact ? (
        <div className="dashboard-section-heading">
          <span>Pending user registrations</span>
        </div>
      ) : (
      <h1 style={{ fontSize: 32 }}>Pending users</h1>)}

      {message && <p>{message}</p>}

      <div
        className="dashboard-scroll-list"
        style={{ maxHeight: 120, overflowY: 'auto', display: 'grid', gap: 12 }}
      >

        {users.map((user) => (
          <div 
            key={user.id}
            className="dashboard-table-row"
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr',
              gap: 8,
              alignItems: 'start',
              padding: '12px 16px',
              minHeight: 90,
              border:
                user.role === 'agent'
                  ? '2px solid var(--accent)'
                  : undefined,
            }}
          >

            <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              <strong>{user.username}</strong>
              <span> — {user.email}</span>
              <span> — {user.role}</span>
            </div>

            <div style={{display: 'flex', gap: 8}}>
              <button 
                type="button" 
                  style={{
                    ...adminButtonStyle, 
                    width: 110, 
                    alignSelf: 'start',
                  }}
                onClick={() => handleApprove(user)}>Approve
              </button>
              <button
                type="button"
                  style={{
                    ...adminButtonStyle,
                    width: 110, 
                    alignSelf: 'start',
                  }}
                onClick={() => handleReject(user)}>Reject
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="dashboard-section-heading" style={{ marginTop: 16 }}>
        <span>List of users</span>
      </div>

      <div 
        className="dashboard-scroll-list" 
        style={{ maxHeight: 300, overflowY: 'auto', display: 'grid', gap: 12 }}
      >
        {allUsers.map((user) => (
          <div
            key={user.id}
            className="dashboard-table-row"
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr',
              gap: 8,
              padding: '12px 16px',
              minHeight: 90,
              border:
                user.role === 'agent'
                  ? '2px solid var(--accent)'
                  : undefined,
            }}
          >
            <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              <strong>{user.username}</strong>
              <span> — {user.email}</span>
              <span> — {user.role}</span>
              <span> — {user.status}</span>
            </div>

            {user.role !== 'admin' && ['approved', 'deactivated', 'rejected'].includes(user.status) && (
              <div style={{ display: 'flex', gap: 8}}>
                <button
                  type="button"
                  style={{
                    ...adminButtonStyle,
                    width: 110,
                    alignSelf: 'start',
                  }}
                  onClick={() =>
                    user.status === 'approved'
                      ? handleDeactivate(user)
                      : handleActivate(user)
                  }
                >
                  {user.status === 'approved' ? 'Deactivate' : 'Activate'}
                </button>

                {['artist', 'agent'].includes(user.role) && (
                  <button
                    type="button"
                    style={{
                      ...adminButtonStyle,
                      width: 180,
                      alignSelf: 'start',
                    }}
                    onClick={() => handleChangeRole(user)}
                  >
                    {user.role === 'artist' ? 'Change to agent' : 'Change to artist'}
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}