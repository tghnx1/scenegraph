import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { isAuthRole, login, register, type AuthRole } from '../api/auth'

interface LoginPageProps {
  onLogin: (role: AuthRole, username: string) => void
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
  const [requestedRole, setRequestedRole] = useState<'artist' | 'agent'>('artist')

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
      const role: AuthRole = isAuthRole(response.role) ? response.role : 'artist'
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
                  <select
                    className="h-10 w-full rounded-md border border-[var(--control-border)] bg-[var(--control-bg)] px-3 text-sm text-[var(--text)] outline-none"
                    value={requestedRole}
                    onChange={(event) => setRequestedRole(event.target.value as 'artist' | 'agent')}
                  >
                    <option value="artist">Artist</option>
                    <option value="agent">Agent</option>
                  </select>
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
