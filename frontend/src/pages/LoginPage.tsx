import { useState, type CSSProperties, type FormEvent } from 'react'
import { login, register, type AuthRole } from '../api/auth'
import { useNavigate } from 'react-router-dom'

interface LoginPageProps {
  onLogin: (role: AuthRole, redirect?: boolean) => void
}

const colorVar = (name: string) => `var(${name})`
const colorAlpha = (name: string, percent: number) => `color-mix(in srgb, var(${name}) ${percent}%, transparent)`

const loginButtonStyle: CSSProperties = {
  textDecoration: 'none',
  color: colorVar('--text-muted'),
  padding: '6px 10px',
  borderRadius: 8,
  fontSize: 14,
  fontWeight: 600,
  transition: 'all 120ms ease',
  cursor: 'pointer',
  border: `1px solid ${colorAlpha('--text', 18)}`,
  background: colorAlpha('--text', 6),
  font: 'inherit',
}

const inputStyle: CSSProperties = {
  width: '100%',
  minWidth: 0,
  border: `1px solid ${colorAlpha('--text', 18)}`,
  borderRadius: 8,
  background: colorAlpha('--background', 64),
  color: colorVar('--text'),
  font: 'inherit',
  padding: '10px 12px',
  outline: 'none',
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const navigate = useNavigate()
  const [username, setUsername] = useState(localStorage.getItem('last_username') ?? '')   // for keeping the username in the login mask
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isRegistering, setIsRegistering] = useState(false)
  const [email, setEmail] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [requestedRole, setRequestedRole] = useState<AuthRole>('artist')

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)

    if (isRegistering) {
      const response = await register(
        username,
        email,
        password,
        passwordConfirm,
        requestedRole,
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
        response.role === 'admin' 
          ? 'admin' 
          : response.role === 'agent'
            ? 'agent'
            : 'artist'

      localStorage.setItem('token', response.access_token)
      localStorage.setItem('role', role)
      localStorage.setItem('username', authenticatedUsername)
      localStorage.setItem('last_username', authenticatedUsername)

      if (response.user_id !== undefined) {
        localStorage.setItem('user_id', String(response.user_id))
      }
      
      //console.log('must_change_password:', response.must_change_password)
      if (response.must_change_password)
      {
        navigate('/change-password?forced=true', { replace: true })
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
        <span className="search-query-label">
          {isRegistering ? 'Register Page' : 'Login page'}
        </span>
        <h1 style={{ marginTop: 8, fontSize: 32 }}>
          {isRegistering ? 'Register' : 'Sign in'}
        </h1>
        <form onSubmit={handleSubmit} style={{ display: 'grid', gap: 14, marginTop: 24 }}>
          <label style={{ display: 'grid', gap: 6, color: colorVar('--text-muted'), fontSize: 14 }}>
            Username
            <input
              style={inputStyle}
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
          {isRegistering && (
            <select value={requestedRole} onChange={(e) => setRequestedRole(e.target.value as AuthRole)}>
              <option value="artist">Artist</option>
              <option value="agent">Agent</option>
            </select>
          )}
          <label style={{ display: 'grid', gap: 6, color: colorVar('--text-muted'), fontSize: 14 }}>
            Password
            <input
              style={inputStyle}
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
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
          {error && <p style={{ margin: 0, color: 'var(--danger, #d94848)', fontSize: 14 }}>{error}</p>}
          <button type="submit" style={loginButtonStyle} disabled={isSubmitting}>
            {isSubmitting
              ? isRegistering
                ? 'Registering...'
                : 'Signing in...'
              : isRegistering
                ? 'Register'
                : 'Sign in'}
          </button>
          <button
            type="button"
            style={loginButtonStyle}
            onClick={() => {
              if (!isRegistering) {
                setUsername('')
                setEmail('')
                setPassword('')
                setPasswordConfirm('')
              }
              setIsRegistering(!isRegistering)
              setError('')
            }}
          >
            {isRegistering ? 'Back to sign in' : 'Create account'}
          </button>
        </form>
      </section>
    </div>
  )
}
