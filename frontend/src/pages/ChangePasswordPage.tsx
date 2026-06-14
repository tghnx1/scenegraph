import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { changePassword, type AuthRole } from '../api/auth'

interface ChangePasswordPageProps {
    onLogin?: (role: AuthRole) => void
}

const colorVar = (name: string) => `var(${name})`
const colorAlpha = (name: string, percent: number) => `color-mix(in srgb, var(${name}) ${percent}%, transparent)`

const inputStyle = {
  width: '100%',
  border: `1px solid ${colorAlpha('--text', 18)}`,
  borderRadius: 8,
  background: colorAlpha('--background', 64),
  color: colorVar('--text'),
  font: 'inherit',
  padding: '10px 12px',
  outline: 'none',
}

export function ChangePasswordPage({ onLogin }: ChangePasswordPageProps) {
  const navigate = useNavigate()
  const username = localStorage.getItem('username') ?? ''
  const [searchParams] = useSearchParams()
  const forced = searchParams.get('forced') === 'true'

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newPasswordConfirm, setNewPasswordConfirm] = useState('')
  const [message, setMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setMessage('')
    setIsSubmitting(true)

    try {
        const response = await changePassword(
            username,
            currentPassword,
            newPassword,
            newPasswordConfirm,
        )

        setMessage(response.message)

        if (response.success) {
            setCurrentPassword('')
            setNewPassword('')
            setNewPasswordConfirm('')

            if (forced) {
                const role = localStorage.getItem('role') as AuthRole | null
                if (role) {
                    onLogin?.(role)
                    navigate(role === 'admin' ? '/dashboard' : '/profile')
                }
            }
        }
    } catch {
        setMessage('Password change failed. Please try again')
    } finally {
        setIsSubmitting(false)
    }
}
  return (
    <div style={{ minHeight: '100%', display: 'grid', placeItems: 'center', padding: 24 }}>
      <section
        style={{
          width: 'min(420px, 100%)',
          padding: 24,
          borderRadius: 8,
          background: colorAlpha('--background', 72),
          border: `1px solid ${colorAlpha('--text', 18)}`,
          boxShadow: 'var(--surface-shadow)',
        }}
      >
        <span className="search-query-label">Account</span>
        <h1 style={{ marginTop: 8, fontSize: 32 }}>
            {forced ? 'Change password before continuing' : 'Change password'}
        </h1>

        <form onSubmit={handleSubmit} style={{ display: 'grid', gap: 14, marginTop: 24 }}>
          <label>
            Current password
            <input
              style={inputStyle}
              type="password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              required
            />
          </label>

          <label>
            New password
            <input
              style={inputStyle}
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              required
            />
          </label>

          <label>
            Confirm new password
            <input
              style={inputStyle}
              type="password"
              value={newPasswordConfirm}
              onChange={(event) => setNewPasswordConfirm(event.target.value)}
              required
            />
          </label>

          {message && <p>{message}</p>}

          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Changing password...' : 'Change password'}
          </button>
          {!forced && (
            <button type="button" onClick={() => navigate(-1)}>
                Back
            </button>
          )}
        </form>
      </section>
    </div>
  )
}