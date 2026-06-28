import { login, register, type AuthRole } from '../api/auth'
import { type CSSProperties, useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronDown } from 'lucide-react'
// import { ChevronsUpDown } from 'lucide-react'
import { validateLoginForm, validateRegistrationForm } from '@/shared/lib/validation'

interface LoginPageProps {
  onLogin: (role: AuthRole, redirect?: boolean) => void }

const colorVar = (name: string) => `var(${name})`
const colorAlpha = (name: string, percent: number) =>
  `color-mix(in srgb, var(${name}) ${percent}%, transparent)`

const REGISTRATION_ROLES = [
  {value: 'artist', label: 'Artist'},
  {value: 'agent', label: 'Agent'},
  {value: 'admin', label: 'Admin'},
] as const

type RegistrationRole = (typeof REGISTRATION_ROLES)[number]['value']

function RoleSelect({value, onChange}: {value: RegistrationRole; onChange: (role: RegistrationRole) => void}) {
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const selectedRole = REGISTRATION_ROLES.find((role) => role.value === value) ?? REGISTRATION_ROLES[0]

  useEffect(() => {
    if (!isOpen) return

    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setIsOpen(false)
    }

    document.addEventListener('mousedown', closeOnOutsideClick)
    return () => document.removeEventListener('mousedown', closeOnOutsideClick)
  }, [isOpen])

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        className="flex h-10 w-full min-w-0 items-center justify-between rounded-md border border-[var(--control-border)] bg-[var(--surface-input)] px-3 py-2 text-left text-sm text-[var(--text)] outline-none transition-[border-color,box-shadow] hover:border-[var(--focus-border)] focus-visible:border-[var(--focus-border)] focus-visible:ring-3 focus-visible:ring-[var(--focus-ring)]"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((open) => !open)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') setIsOpen(false)
          if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault()
            setIsOpen(true)
          }
        }}
      >
        <span>{selectedRole.label}</span>
        <ChevronDown className="size-4 text-[var(--text-muted)]" aria-hidden="true" />
        {/* <ChevronsUpDown className="size-4 text-[var(--text-muted)]" aria-hidden="true" /> */}
      </button>
      {isOpen && (
        <div
          className="absolute left-0 right-0 top-[calc(100%+6px)] z-30 grid gap-1 rounded-xl border border-[var(--surface-border)] bg-[var(--surface-dropdown)] p-1.5 shadow-[var(--surface-shadow)]"
          role="listbox"
          aria-label="Requested role"
        >
          {REGISTRATION_ROLES.map((role) => (
            <button
              type="button"
              className="rounded-lg border border-transparent bg-transparent px-3 py-2 text-left text-sm text-[var(--text)] outline-none transition-colors hover:bg-[var(--control-bg)] focus-visible:bg-[var(--control-bg)]"
              role="option"
              aria-selected={role.value === value}
              key={role.value}
              onClick={() => {
                onChange(role.value)
                setIsOpen(false)
              }}
            >
              {role.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

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
  const [error, setError] = useState(() => {
    const message = sessionStorage.getItem('auth_message') ?? ''
    sessionStorage.removeItem('auth_message')
    return message
  })

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isRegistering, setIsRegistering] = useState(false)
  const [email, setEmail] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [requestedRole, setRequestedRole] = useState<RegistrationRole>('artist') 

  useEffect(() => {
    const showLoginForm = () => {
      setError('')
      setIsRegistering(false)
    }
    window.addEventListener('show-login-form', showLoginForm)
    return () => {
      window.removeEventListener('show-login-form', showLoginForm)
    }
  }, [])

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    const cleanUsername = username.trim()
    const cleanEmail = email.trim()

    if (isRegistering) {
      const validationError = validateRegistrationForm(cleanUsername, cleanEmail, password, passwordConfirm)
      if (validationError) {
        setError(validationError)
        return
      }

      setIsSubmitting(true)
      const response = await register(
        cleanUsername,
        cleanEmail,
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

    const validationError = validateLoginForm(cleanUsername, password)
    if (validationError) {
      setError(validationError)
      return
    }

    setIsSubmitting(true)

    try {
      if (isRegistering) {
        const response = await register(cleanUsername, cleanEmail, password, passwordConfirm, requestedRole)
        if (!response.success) {
          setError(response.message)
          return
        }

        setError('Registration successful. Please wait for admin approval.')
        setIsRegistering(false)
        setPassword('')
        setPasswordConfirm('')
        setEmail('')
        return
      }

      const response = await login(cleanUsername, password)
      if (!response.success || !response.access_token) {
        setError(response.message || 'Invalid username or password')
        return
      }
      sessionStorage.removeItem('auth_message')
      setError('')

      const authenticatedUsername = response.username ?? cleanUsername
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

      if (response.artist_id) {
         localStorage.setItem('artist_id', String(response.artist_id))
      } else {
         localStorage.removeItem('artist_id')
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
            <RoleSelect
              value={requestedRole}
              onChange={setRequestedRole}
            />
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
