import { useEffect, useState } from 'react'
import { changeUserRole, approveUser, rejectUser, getPendingUsers, getUsers, 
  deactivateUser, activateUser, type PendingUser, type UserItem, 
  getArtistClaims, approveArtistClaim, rejectArtistClaim, type ArtistClaim, } from '../api/auth'

interface AdminUsersPageProps { 
  compact?: boolean
  onActivityChanged?: () => Promise<void>       //to update directly the log, the child adminuserpage has to ask the dashboardpage.
}  

export function AdminUsersPage({ compact = false, onActivityChanged, }: AdminUsersPageProps) {
  const [users, setUsers] = useState<PendingUser[]>([])
  const [message, setMessage] = useState('')
  const [allUsers, setAllUsers] = useState<UserItem[]>([])
  const [claims, setClaims] = useState<ArtistClaim[]>([])

  const adminButtonStyle = {
    padding: '8px 12px',
    background: 'color-mix(in srgb, var(--background) 88%, var(--text) 8%)',
    border: '1px solid color-mix(in srgb, var(--text) 20%, transparent)',
    borderRadius: 8,
    cursor: 'pointer',
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

  const loadClaims = async () => {
    try {
      const response = await getArtistClaims()
      setClaims(response.claims.filter((claim) => claim.status === 'pending'))
    } catch (error) {
      console.error(error)
    }
  }

  useEffect(() => {
    loadUsers()
    loadAllUsers()
    loadClaims()
  }, [])



  const handleApprove = async (user: PendingUser) => {
    //if (!confirm(`Approve ${user.username}?`)) return

    await approveUser(user.id)
    //setMessage(response.message)
    await loadUsers()
    await loadAllUsers()
    await onActivityChanged?.()
  }

  const handleReject = async (user: PendingUser) => {
  if (!confirm(`Reject ${user.username}?`))
    return

    await rejectUser(user.id)
    //setMessage(response.message)
    await loadUsers()
    await loadAllUsers()
    await onActivityChanged?.()
  }

  const handleDeactivate = async (user: UserItem) => {
    if (!confirm(`Deactivate ${user.username}?`)) return

    await deactivateUser(user.id)
    //setMessage(response.message)
    await loadUsers()
    await loadAllUsers()
    await onActivityChanged?.()
  }

  const handleActivate = async (user: UserItem) => {
    //if (!confirm(`Activate ${user.username}?`)) return

    await activateUser(user.id)
    //setMessage(response.message)
    await loadUsers()
    await loadAllUsers()
    await onActivityChanged?.()
  }

  const handleChangeRole = async (user: UserItem) => {
    const newRole = user.role === 'artist' ? 'agent' : 'artist'

    //if (!confirm(`Change ${user.username} to ${newRole}?`)) return

    await changeUserRole(user.id, newRole)
    //setMessage(response.message)
    await loadUsers()
    await loadAllUsers()
    await onActivityChanged?.()
  }

  const handleApproveClaim = async (claim: ArtistClaim) => {
    await approveArtistClaim(claim.id)
    setMessage(`Claim approved for ${claim.artist_name}`)
    await loadClaims()
    await loadUsers()
    await onActivityChanged?.()
  }

  const handleRejectClaim = async (claim: ArtistClaim) => {
    if (!window.confirm(`Reject claim for ${claim.artist_name}?`)) return

    await rejectArtistClaim(claim.id)
    setMessage(`Claim rejected for ${claim.artist_name}`)
    await loadClaims()
    await onActivityChanged?.()
  }

  return (
    <section style={{ display: 'grid', gap: 12}}>
      {compact ? (
        <div className="dashboard-section-heading">
          <span>Pending user registrations and artist claims</span>
        </div>
      ) : (
      <h1 style={{ fontSize: 32 }}>Pending users</h1>)}

      {message && <p>{message}</p>}

      <div
        className="dashboard-scroll-list"
        style={{ maxHeight: 130, overflowY: 'auto', display: 'grid', gap: 12, paddingRight: 16, paddingTop: 4 }}
      >

        {users.map((user) => (
          <div 
            key={user.id}
            className="dashboard-table-row"
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr',
              gap: 8,
              padding: '12px 16px',
              minHeight: 120,
              background: 'color-mix(in srgb, var(--background) 82%, var(--text) 8%)',
              borderRadius: 12,
              paddingRight: 12,
              border:
                user.role === 'agent'
                  ? '2px solid var(--accent)'
                  : '1px solid color-mix(in srgb, var(--text) 18%, transparent)',
            }}
          >

            <div style={{ whiteSpace: 'normal', overflow: 'visible', textOverflow: 'ellipsis' }}>
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

        {claims.map((claim) => (
          <div
            key={`claim-${claim.id}`}
            className="dashboard-table-row"
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr',
              gap: 8,
              padding: '12px 16px',
              minHeight: 120,
              alignItems: 'start',
              background: 'color-mix(in srgb, var(--background) 82%, var(--text) 8%)',
              borderRadius: 12,
              border: '2px solid color-mix(in srgb, var(--accent) 65%, var(--text) 20%)',
            }}
          >
            <div style={{ whiteSpace: 'normal', overflow: 'visible' }}>
              <strong>Artist claim</strong>
              <span> — {claim.username}</span>
              <span> — {claim.email}</span>
              <span> — claims: {claim.artist_name}</span>
            </div>

            <p style={{ margin: 0, fontSize: 13, color: 'var(--text-muted)' }}>
              Reason: {claim.reason}
            </p>

            <div style={{ display: 'flex', gap: 8 }}>
              <button
                type="button"
                style={{
                  ...adminButtonStyle,
                  width: 110,
                  alignSelf: 'start',
                }}
                onClick={() => handleApproveClaim(claim)}
              >
                Approve
              </button>

              <button
                type="button"
                style={{
                  ...adminButtonStyle,
                  width: 110,
                  alignSelf: 'start',
                }}
                onClick={() => handleRejectClaim(claim)}
              >
                Reject
              </button>
            </div>
          </div>
        ))}

      <div className="dashboard-section-heading" style={{ marginTop: 8, marginBottom: 4 }}>
        <span>List of users</span>
      </div>

      <div 
        className="dashboard-scroll-list" 
        style={{ maxHeight: 300, overflowY: 'auto', display: 'grid', gap: 12, paddingRight: 16, paddingTop: 4 }}
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
              minHeight: 120,
              paddingRight: 12,
              background: 'color-mix(in srgb, var(--background) 82%, var(--text) 8%)',
              borderRadius: 12,

              border:
                user.role === 'agent'
                  ? '2px solid var(--accent)'
                  : '1px solid color-mix(in srgb, var(--text) 18%, transparent)',
            }}
          >
            <div style={{ whiteSpace: 'normal', overflow: 'visible', textOverflow: 'ellipsis' }}>
              <strong>{user.username}</strong>
              <span> — {user.email}</span>
              <span> — {user.role}</span>
              <span> — {user.status}</span>
            </div>

            {['approved', 'deactivated', 'rejected'].includes(user.status) && (
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
