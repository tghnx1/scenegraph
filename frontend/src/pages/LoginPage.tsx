import { useState, type CSSProperties, type FormEvent } from 'react'
import { changePassword, isAuthRole, login, register, type AuthRole } from '../api/auth'

interface LoginPageProps {
  onLogin: (role: AuthRole, username: string) => void
}

const colorVar = (name: string) => `var(${name})`
const colorAlpha = (name: string, percent: number) => `color-mix(in srgb, var(${name}) ${percent}%, transparent)`

export function LoginPage({ onLogin }: LoginPageProps) {
  const [username, setUsername] = useState(localStorage.getItem('last_username') ?? '')   // for keeping the username in the login mask
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [mustChangePassword, setMustChangePassword] = useState(false)
  const [newPassword, setNewPassword] = useState('')
  const [newPasswordConfirm, setNewPasswordConfirm] = useState('')
  const [isRegistering, setIsRegistering] = useState(false)
  const [email, setEmail] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)

    if (mustChangePassword) {
      const response = await changePassword(
        username,
        password,
        newPassword,
        newPasswordConfirm,
      )

      if (!response.success) {
        setError(response.message)
        setIsSubmitting(false)
        return
      }

      setError('Password changed. Please sign in with your new password.')
      setPassword('')
      setNewPassword('')
      setNewPasswordConfirm('')
      setMustChangePassword(false)
      setIsSubmitting(false)
      return
    }

    if (isRegistering) {
      const response = await register(
        username,
        email,
        password,
        passwordConfirm,
      )

      if (!response.success) {
        setError(response.message)
        setIsSubmitting(false)
        return
      }

      setError('Registration successful. Please wait for admin approval.')
      setIsRegistering(false)
      setPassword('')
      setPasswordConfirm('')
      setEmail('')
      setIsSubmitting(false)
      return
    }

    try {
      const response = await login(username, password)

      if (!response.success || !response.access_token) {
        setError(response.message || 'Invalid username or password')
        return
      }

      const authenticatedUsername = response.username ?? username
      const role: AuthRole =
        response.role === 'admin' ? 'admin' : 'user'

      localStorage.setItem('token', response.access_token)
      localStorage.setItem('role', role)
      localStorage.setItem('username', authenticatedUsername)
      localStorage.setItem('last_username', authenticatedUsername)

      if (response.user_id !== undefined) {
        localStorage.setItem('user_id', String(response.user_id))
      }
      if (response.artist_id !== undefined) {
        localStorage.setItem('artist_id', String(response.artist_id))
      } else {
        localStorage.removeItem('artist_id')
      }

      if (response.must_change_password)
      {
        setMustChangePassword(true)
        setError('You must change your password before continuing.')
        return
      }
      onLogin(role)
    } catch {
      setError('Login failed. Please try again.')
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
        <span className="search-query-label">Login page</span>
        <h1 style={{ marginTop: 8, fontSize: 32 }}>Sign in</h1>
        <form onSubmit={handleSubmit} style={{ display: 'grid', gap: 14, marginTop: 24 }}>
          <label style={{ display: 'grid', gap: 6, color: colorVar('--text-muted'), fontSize: 14 }}>
            Username
            <input
              style={authInputStyle}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              required
            />
          </label>
          {isRegistering && (
            <label style={{ display: 'grid', gap: 6, color: colorVar('--text-muted'), fontSize: 14 }}>
              Email
              <input
                style={inputStyle}
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </label>
          )}
          <label style={{ display: 'grid', gap: 6, color: colorVar('--text-muted'), fontSize: 14 }}>
            Password
            <PasswordInput
              value={password}
              onChange={setPassword}
              autoComplete="current-password"
              required
            />
          </label>
          {isRegistering && (
            <label style={{ display: 'grid', gap: 6, color: colorVar('--text-muted'), fontSize: 14 }}>
              Confirm password
              <input
                style={inputStyle}
                type="password"
                value={passwordConfirm}
                onChange={(event) => setPasswordConfirm(event.target.value)}
                required
              />
            </label>
          )}
          {mustChangePassword && (
            <>
              <label style={{ display: 'grid', gap: 6, color: colorVar('--text-muted'), fontSize: 14 }}>
                New password
                <input
                  style={inputStyle}
                  type="password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                />
              </label>

              <label style={{ display: 'grid', gap: 6, color: colorVar('--text-muted'), fontSize: 14 }}>
                Confirm new password
                <input
                  style={inputStyle}
                  type="password"
                  value={newPasswordConfirm}
                  onChange={(event) => setNewPasswordConfirm(event.target.value)}
                />
              </label>
            </>
          )}
          {error && <p style={{ margin: 0, color: 'var(--danger, #d94848)', fontSize: 14 }}>{error}</p>}
          <button type="submit" style={loginButtonStyle} disabled={isSubmitting}>
            {isSubmitting
              ? isRegistering
                ? 'Registering...'
                : mustChangePassword
                  ? 'Changing password...'
                  : 'Signing in...'
              : isRegistering
                ? 'Register'
                : mustChangePassword
                  ? 'Change password'
                  : 'Sign in'}
          </button>
          <button
            type="button"
            style={loginButtonStyle}
            onClick={() => {
              setIsRegistering(!isRegistering)
              setError('')
            }}
          >
            {isRegistering ? 'Back to sign in' : 'Create account'}
          </button>
        </form>
        <p style={{ margin: '18px 0 0', color: colorVar('--text-muted'), fontSize: 14 }}>
          No account yet?{' '}
          <Link to="/register" style={{ color: colorVar('--text'), fontWeight: 700 }}>
            Create one
          </Link>
        </p>
      </section>
    </div>
  )
}
