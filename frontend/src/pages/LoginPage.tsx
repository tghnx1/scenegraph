import { useState, type FormEvent } from 'react'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { changePassword, isAuthRole, login, register, type AuthRole } from '../api/auth'

interface LoginPageProps {
  onLogin: (role: AuthRole, username: string) => void
}

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
      const role: AuthRole = isAuthRole(response.role) ? response.role : 'user'

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

      if (response.must_change_password) {
        setMustChangePassword(true)
        setError('You must change your password before continuing.')
        return
      }
      onLogin(role, authenticatedUsername)
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
          <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">Login page</span>
          <CardTitle className="mt-2 text-[32px]">Sign in</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="grid gap-3.5">
            <Label>
              Username
              <Input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
                required
              />
            </Label>
            {isRegistering && (
              <Label>
                Email
                <Input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
              </Label>
            )}
            <Label>
              Password
              <Input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                required
              />
            </Label>
            {isRegistering && (
              <Label>
                Confirm password
                <Input
                  type="password"
                  value={passwordConfirm}
                  onChange={(event) => setPasswordConfirm(event.target.value)}
                  required
                />
              </Label>
            )}
            {mustChangePassword && (
              <>
                <Label>
                  New password
                  <Input
                    type="password"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                  />
                </Label>

                <Label>
                  Confirm new password
                  <Input
                    type="password"
                    value={newPasswordConfirm}
                    onChange={(event) => setNewPasswordConfirm(event.target.value)}
                  />
                </Label>
              </>
            )}
            {error && <p className="m-0 text-sm text-[var(--danger,#d94848)]">{error}</p>}
            <Button type="submit" disabled={isSubmitting}>
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
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setIsRegistering(!isRegistering)
                setError('')
              }}
            >
              {isRegistering ? 'Back to sign in' : 'Create account'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
