import { useEffect, useState } from 'react'
import { approveUser, rejectUser, getPendingUsers, type PendingUser } from '../api/auth'

export function AdminUsersPage() {
  const [users, setUsers] = useState<PendingUser[]>([])
  const [message, setMessage] = useState('')

  //const loadUsers = async () => {
    //const response = await getPendingUsers()
    //setUsers(response.users)
  //}
  const loadUsers = async () => {
  try {
    console.log('admin username:', localStorage.getItem('username'))
    const response = await getPendingUsers()
    console.log('pending users response:', response)
    setUsers(response.users)
  } catch (error) {
    console.error(error)
    setMessage('Could not load pending users')
  }
    }

  useEffect(() => {
    loadUsers()
  }, [])

  const handleApprove = async (user: PendingUser) => {
    if (!confirm(`Approve ${user.username}?`)) return

    const response = await approveUser(user.id)
    setMessage(response.message)
    await loadUsers()
  }

  const handleReject = async (user: PendingUser) => {
  if (!confirm(`Reject ${user.username}?`))
    return

    const response = await rejectUser(user.id)
    setMessage(response.message)
    await loadUsers()
}

  return (
    <section>
      <h1 style={{ fontSize: 32 }}>Pending users</h1>
      {message && <p>{message}</p>}

      {users.map((user) => (
        <div key={user.id}>
          <strong>{user.username}</strong> — {user.email}
          <button onClick={() => handleApprove(user)}>Approve</button>
          <button onClick={() => handleReject(user)}>Reject</button>
        </div>
      ))}
    </section>
  )
}