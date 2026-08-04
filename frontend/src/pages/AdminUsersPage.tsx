import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import {
  changeUserRole,
  approveUser,
  rejectUser,
  getPendingUsers,
  getUsers,
  getRegistrationSettings,
  getUiSettings,
  updateRegistrationSettings,
  updateUiSettings,
  deactivateUser,
  activateUser,
  unbindArtist,
  type PendingUser,
  type UserItem,
} from '../api/auth'

interface AdminUsersPageProps {
  compact?: boolean
  refreshVersion?: number
  onActivityChanged?: () => Promise<void>       //to update directly the log, the child adminuserpage has to ask the dashboardpage.
}

export function AdminUsersPage({ compact = false, refreshVersion = 0, onActivityChanged, }: AdminUsersPageProps) {
  const [users, setUsers] = useState<PendingUser[]>([])
  const [message, setMessage] = useState('')
  const [allUsers, setAllUsers] = useState<UserItem[]>([])
  const [autoApprovePendingUsers, setAutoApprovePendingUsers] = useState(false)
  const [showGraphTab, setShowGraphTab] = useState(true)
  const autoApprovedPendingUserIdsRef = useRef<Set<number>>(new Set())

  const toRaUrl = (value: string) =>
    value.startsWith('http')
      ? value
      : `https://ra.co${value.startsWith('/') ? value : `/${value}`}`

  const adminButtonStyle = {
    padding: '8px 12px',
    background: 'color-mix(in srgb, var(--background) 88%, var(--text) 8%)',
    border: '1px solid color-mix(in srgb, var(--text) 20%, transparent)',
    borderRadius: 8,
    cursor: 'pointer',
  }

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

  const loadRegistrationSettings = async () => {
    try {
      const response = await getRegistrationSettings()
      setAutoApprovePendingUsers(response.auto_approve_pending_users)
    } catch (error) {
      console.error(error)
      setMessage('Could not load registration settings')
    }
  }

  const loadUiSettings = async () => {
    try {
      const response = await getUiSettings()
      setShowGraphTab(response.show_graph_tab)
    } catch (error) {
      console.error(error)
      setMessage('Could not load UI settings')
    }
  }

  useEffect(() => {
    loadUsers()
    loadAllUsers()
    loadRegistrationSettings()
    loadUiSettings()
  }, [refreshVersion])

  useEffect(() => {
    if (!autoApprovePendingUsers) {
      autoApprovedPendingUserIdsRef.current.clear()
      return
    }

    let cancelled = false

    const approveQueuedPendingUsers = async () => {
      for (const user of users) {
        if (cancelled) return
        if (autoApprovedPendingUserIdsRef.current.has(user.id)) continue
        autoApprovedPendingUserIdsRef.current.add(user.id)

        try {
          await approveUser(user.id)
          await loadUsers()
          await loadAllUsers()
          await onActivityChanged?.()
        } catch (error) {
          setMessage(error instanceof Error ? error.message : 'Failed to auto-approve user')
          return
        }
      }
    }

    void approveQueuedPendingUsers()

    return () => {
      cancelled = true
    }
  }, [autoApprovePendingUsers, onActivityChanged, users])

  const handleToggleAutoApprove = async (event: ChangeEvent<HTMLInputElement>) => {
    const enabled = event.target.checked
    setAutoApprovePendingUsers(enabled)

    try {
      await updateRegistrationSettings(enabled)
      setMessage('')
    } catch (error) {
      setAutoApprovePendingUsers(!enabled)
      setMessage(error instanceof Error ? error.message : 'Failed to update registration settings')
    }
  }

  const handleToggleGraphTab = async (event: ChangeEvent<HTMLInputElement>) => {
    const enabled = event.target.checked
    setShowGraphTab(enabled)

    try {
      await updateUiSettings(enabled)
      setMessage('')
    } catch (error) {
      setShowGraphTab(!enabled)
      setMessage(error instanceof Error ? error.message : 'Failed to update UI settings')
    }
  }


  const handleApprove = async (user: PendingUser) => {
    //if (!confirm(`Approve ${user.username}?`)) return
    try {
      await approveUser(user.id)
      setMessage('')
      await loadUsers()
      await loadAllUsers()
      await onActivityChanged?.()
    } catch (error) {
      setMessage(error instanceof Error ? error.message: 'Failed to approve user')
    }
  }

  const handleReject = async (user: PendingUser) => {
    if (!confirm(`Reject ${user.username}?`))
      return

    try{
      await rejectUser(user.id)
      setMessage('')
      await loadUsers()
      await loadAllUsers()
      await onActivityChanged?.()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Failed to reject user')
    }
  }

  const handleDeactivate = async (user: UserItem) => {
    if (!confirm(`Deactivate ${user.username}?`)) return

    try{
      await deactivateUser(user.id)
      setMessage('')
      await loadUsers()
      await loadAllUsers()
      await onActivityChanged?.()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Failed to deactivate user')
    }
  }

  const handleActivate = async (user: UserItem) => {
    //if (!confirm(`Activate ${user.username}?`)) return

    try {
      await activateUser(user.id)
      setMessage('')
      await loadUsers()
      await loadAllUsers()
      await onActivityChanged?.()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Failed to activate user')
    }
  }

  const handleUnbindArtist = async (user: UserItem) => {
    if (!confirm(`Unbind the artist profile from ${user.username}?`)) return

    try {
      await unbindArtist(user.id)
      setMessage('')
      await loadUsers()
      await loadAllUsers()
      await onActivityChanged?.()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Failed to unbind artist')
    }
  }

  const handleChangeRole = async (user: UserItem) => {
    const newRole = user.role === 'artist' ? 'agent' : 'artist'

    //if (!confirm(`Change ${user.username} to ${newRole}?`)) return
    try{ 
      await changeUserRole(user.id, newRole)
      setMessage('')
      await loadUsers()
      await loadAllUsers()
      await onActivityChanged?.()
    } catch (error) {
      setMessage(error instanceof Error ? error.message: 'Failed to change role')
    }
  }

  return (
    <section className="min-w-0" style={{ display: 'grid', gap: 12}}>
      {compact ? (
        <div
          className="mb-3 flex flex-wrap items-center justify-between gap-2"
          style={{ minHeight:38 }}
        >
          <span>Pending user registrations</span>
        </div>
      ) : (
      <h1 style={{ fontSize: 32 }}>Pending users</h1>)}


      <div
        className="dashboard-scroll-list"
        style={{ maxHeight: 130, overflowY: 'auto', display: 'grid', gap: 12, paddingRight: 16, paddingTop: 4 }}
      >
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '8px 12px',
            borderRadius: 10,
            border: '1px solid color-mix(in srgb, var(--text) 18%, transparent)',
            background: 'color-mix(in srgb, var(--background) 88%, var(--text) 6%)',
          }}
          >
            <input
              type="checkbox"
              checked={autoApprovePendingUsers}
              onChange={handleToggleAutoApprove}
            />
          <span>Auto-approve new registrations</span>
        </label>
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '8px 12px',
            borderRadius: 10,
            border: '1px solid color-mix(in srgb, var(--text) 18%, transparent)',
            background: 'color-mix(in srgb, var(--background) 88%, var(--text) 6%)',
          }}
        >
          <input
            type="checkbox"
            checked={showGraphTab}
            onChange={handleToggleGraphTab}
          />
          <span>Show Graph tab</span>
        </label>
        {users.map((user) => (
              <div
                key={`user-${user.id}`}
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

                <div style={{ display: 'grid', gap: 4 }}>
                  <div style={{ whiteSpace: 'normal', overflow: 'visible', textOverflow: 'ellipsis' }}>
                    <strong>{user.username}</strong>
                    <span> — {user.email}</span>
                    <span> — {user.role}</span>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, color: 'var(--text-muted)', fontSize: 13 }}>
                    <span>Registration: {new Date(user.created_at).toLocaleString()}</span>
                    {user.artist_name && <span>Artist: {user.artist_name}</span>}
                    {user.artist_source && <span>Source: {user.artist_source === 'resident_advisor' ? 'Resident Advisor' : 'User-created profile'}</span>}
                    {user.artist_instagram_url && (
                      <a href={user.artist_instagram_url} target="_blank" rel="noreferrer noopener">
                        Instagram
                      </a>
                    )}
                    {user.artist_content_url && (
                      <a href={toRaUrl(user.artist_content_url)} target="_blank" rel="noreferrer noopener">
                        RA page
                      </a>
                    )}
                  </div>
                  {user.role === 'artist' && !user.artist_name && (
                    <p style={{ margin: 0, fontSize: 13, color: 'var(--danger, #d94848)' }}>
                      No artist profile selected during registration.
                    </p>
                  )}
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

      <div className="dashboard-section-heading" style={{ marginTop: 8, marginBottom: 4 }}>
        <span>List of users</span>
      </div>

      {message && 
        (<p style={{ color: 'var(--danger, #d94848', margin: 0 }}>
          {message}
        </p>
      )}

      <div
        className="dashboard-scroll-list"
        style={{ maxHeight: 290, overflowY: 'auto', display: 'grid', gap: 12, paddingRight: 16, paddingTop: 4 }}
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
            <div className="min-w-0 break-words" style={{ display: 'grid', gap: 4 }}>
              <div style={{ whiteSpace: 'normal', overflow: 'visible', textOverflow: 'ellipsis' }}>
                <strong>{user.username}</strong>
                <span> — {user.email}</span>
                <span> — {user.role}</span>
                <span> — {user.status}</span>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, color: 'var(--text-muted)', fontSize: 13 }}>
                <span>Registration: {new Date(user.created_at).toLocaleString()}</span>
                {user.artist_name && <span>Artist: {user.artist_name}</span>}
                {user.artist_source && <span>Source: {user.artist_source === 'resident_advisor' ? 'Resident Advisor' : 'User-created profile'}</span>}
                {user.artist_instagram_url && (
                  <a href={user.artist_instagram_url} target="_blank" rel="noreferrer noopener">
                    Instagram
                  </a>
                )}
                {user.artist_content_url && (
                  <a href={toRaUrl(user.artist_content_url)} target="_blank" rel="noreferrer noopener">
                    RA page
                  </a>
                )}
              </div>
            </div>

            {['approved', 'deactivated'].includes(user.status) && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8}}>
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
                {user.artist_id != null && (
                  <button
                    type="button"
                    style={{
                      ...adminButtonStyle,
                      width: 140,
                      alignSelf: 'start',
                    }}
                    onClick={() => handleUnbindArtist(user)}
                  >
                    Unbind artist
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
