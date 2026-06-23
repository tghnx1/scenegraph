import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronDown } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { isAuthRole, login, register, type AuthRole } from '../api/auth'

interface LoginPageProps {
  onLogin: (role: AuthRole, username: string) => void
}

const REGISTRATION_ROLES = [
  {value: 'user', label: 'User'},
  {value: 'contributor', label: 'Agent'},
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

export function LoginPage({ onLogin }: LoginPageProps) {
  const navigate = useNavigate()
  const [username, setUsername] = useState(localStorage.getItem('last_username') ?? '')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isRegistering, setIsRegistering] = useState(false)
  const [email, setEmail] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [requestedRole, setRequestedRole] = useState<RegistrationRole>('user')

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)

    try {
      if (isRegistering) {
        const response = await register(username, email, password, passwordConfirm, requestedRole)
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

      const response = await login(username, password)
      if (!response.success || !response.access_token) {
        setError(response.message || 'Invalid username or password')
        return
      }

      const authenticatedUsername = response.username ?? username
      const role: AuthRole = isAuthRole(response.role) ? response.role : 'user'
      localStorage.setItem('token', response.access_token)
      localStorage.setItem('role', role)
      localStorage.setItem('username', authenticatedUsername)
      localStorage.setItem('last_username', authenticatedUsername)

      if (response.user_id !== undefined) localStorage.setItem('user_id', String(response.user_id))
      if (response.artist_id !== undefined) {
        localStorage.setItem('artist_id', String(response.artist_id))
      } else {
        localStorage.removeItem('artist_id')
      }

      if (response.must_change_password) {
        navigate('/change-password?forced=true', { replace: true })
        return
      }

      onLogin(role, authenticatedUsername)
      navigate(role === 'admin' ? '/dashboard' : '/graph')
    } catch {
      setError('Login failed. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="grid min-h-full place-items-center p-6">
      <Card className="w-full max-w-[420px] bg-[color-mix(in_srgb,var(--background)_72%,transparent)]">
        <CardHeader>
          <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">
            {isRegistering ? 'Register page' : 'Login page'}
          </span>
          <CardTitle className="mt-2 text-[32px]">{isRegistering ? 'Register' : 'Sign in'}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="grid gap-3.5">
            <Label>Username<Input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required /></Label>
            {isRegistering && (
              <>
                <Label>Email<Input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></Label>
                <Label>
                  Requested role
                  <RoleSelect value={requestedRole} onChange={setRequestedRole} />
                </Label>
              </>
            )}
            <Label>Password<Input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required /></Label>
            {isRegistering && <Label>Confirm password<Input type="password" value={passwordConfirm} onChange={(event) => setPasswordConfirm(event.target.value)} required /></Label>}
            {error && <p className="m-0 text-sm text-[var(--danger,#d94848)]">{error}</p>}
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? (isRegistering ? 'Registering...' : 'Signing in...') : (isRegistering ? 'Register' : 'Sign in')}
            </Button>
            <Button type="button" variant="secondary" onClick={() => { setIsRegistering(!isRegistering); setError('') }}>
              {isRegistering ? 'Back to sign in' : 'Create account'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
