import { useEffect, useState } from 'react'
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
    <section style={{ display: 'grid', gap: 12}}>
      {compact ? (
        <div className="dashboard-section-heading">
          <span>Pending user registrations</span>
        </div>
      ) : (
      <h1 style={{ fontSize: 32 }}>Pending users</h1>)}

      {message && <p>{message}</p>}

      {users.map((user) => (
        <div 
          key={user.id}
          className="dashboard-table-row"
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr',
            gap: 10,
            alignItems: 'start',
          }}
        >
          <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            <strong>{user.username}</strong>
            <span> — {user.email}</span>
          </div>

          <div style={{display: 'flex', gap: 8}}>
            <button type="button" onClick={() => handleApprove(user)}>Approve</button>
            <button type="button" onClick={() => handleReject(user)}>Reject</button>
          </div>
        </div>
      ))}

      <div className="dashboard-section-heading" style={{ marginTop: 16 }}>
        <span>List of users</span>
      </div>

      <div style={{ display: 'grid', gap: 12 }}>
        {allUsers.map((user) => (
          <div
            key={user.id}
            className="dashboard-table-row"
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr',
              gap: 10,
            }}
          >
            <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              <strong>{user.username}</strong>
              <span> — {user.email}</span>
              <span> — {user.status}</span>
            </div>

            {user.role !== 'admin' && user.status === 'approved' && (
              <div style={{ display: 'flex', gap: 8 }}>
                <button type="button" onClick={() => handleDeactivate(user)}>
                  Deactivate
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}