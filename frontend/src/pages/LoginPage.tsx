import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { getFallbackRole, isAuthRole, login, type AuthRole } from '../api/auth'
import { authButtonStyle, authInputStyle, PasswordInput } from './components/PasswordToggle'

interface LoginPageProps {
  onLogin: (role: AuthRole, username: string) => void
}

const colorVar = (name: string) => `var(${name})`
const colorAlpha = (name: string, percent: number) => `color-mix(in srgb, var(${name}) ${percent}%, transparent)`

export function LoginPage({ onLogin }: LoginPageProps) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)

    try {
      const response = await login(username, password)

      if (!response.success || !response.access_token) {
        setError(response.message || 'Invalid username or password')
        return
      }

      const authenticatedUsername = response.username ?? username
      const responseRole = response.role ?? null
      const role = isAuthRole(responseRole) ? responseRole : getFallbackRole(authenticatedUsername)

      localStorage.setItem('token', response.access_token)
      localStorage.setItem('role', role)
      localStorage.setItem('username', authenticatedUsername)
      if (response.user_id !== undefined) {
        localStorage.setItem('user_id', String(response.user_id))
      }

      onLogin(role, authenticatedUsername)
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
          <label style={{ display: 'grid', gap: 6, color: colorVar('--text-muted'), fontSize: 14 }}>
            Password
            <PasswordInput
              value={password}
              onChange={setPassword}
              autoComplete="current-password"
              required
            />
          </label>
          {error && <p style={{ margin: 0, color: 'var(--danger, #d94848)', fontSize: 14 }}>{error}</p>}
          <button type="submit" style={authButtonStyle} disabled={isSubmitting}>
            {isSubmitting ? 'Signing in...' : 'Sign in'}
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
