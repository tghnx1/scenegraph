import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { register } from '../api/auth'
import { authButtonStyle, authInputStyle, PasswordInput } from './components/PasswordToggle'

const colorVar = (name: string) => `var(${name})`
const colorAlpha = (name: string, percent: number) => `color-mix(in srgb, var(${name}) ${percent}%, transparent)`

export function RegisterPage() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setSuccess('')

    if (password !== passwordConfirm) {
      setError('Passwords do not match')
      return
    }

    setIsSubmitting(true)

    try {
      const response = await register(username, email, password, passwordConfirm)

      if (!response.success) {
        setError(response.message || 'Registration failed')
        return
      }

      setSuccess(response.message || 'Registration successful')
      setTimeout(() => navigate('/login'), 600)
    } catch {
      setError('Registration failed. Please try again.')
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
        <span className="search-query-label">Register page</span>
        <h1 style={{ marginTop: 8, fontSize: 32 }}>Create account</h1>
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
            Email
            <input
              style={authInputStyle}
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
            />
          </label>
          <label style={{ display: 'grid', gap: 6, color: colorVar('--text-muted'), fontSize: 14 }}>
            Password
            <PasswordInput
              value={password}
              onChange={setPassword}
              autoComplete="new-password"
              required
            />
          </label>
          <label style={{ display: 'grid', gap: 6, color: colorVar('--text-muted'), fontSize: 14 }}>
            Confirm password
            <PasswordInput
              value={passwordConfirm}
              onChange={setPasswordConfirm}
              autoComplete="new-password"
              ariaShowLabel="Show password confirmation"
              ariaHideLabel="Hide password confirmation"
              required
            />
          </label>
          {error && <p style={{ margin: 0, color: 'var(--danger, #d94848)', fontSize: 14 }}>{error}</p>}
          {success && <p style={{ margin: 0, color: 'var(--success, #2f8f5b)', fontSize: 14 }}>{success}</p>}
          <button type="submit" style={authButtonStyle} disabled={isSubmitting}>
            {isSubmitting ? 'Creating account...' : 'Create account'}
          </button>
        </form>
        <p style={{ margin: '18px 0 0', color: colorVar('--text-muted'), fontSize: 14 }}>
          Already have an account?{' '}
          <Link to="/login" style={{ color: colorVar('--text'), fontWeight: 700 }}>
            Sign in
          </Link>
        </p>
      </section>
    </div>
  )
}
