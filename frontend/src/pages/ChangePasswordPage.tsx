import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { changePassword, isAuthRole, type AuthRole } from '../api/auth'

interface ChangePasswordPageProps {
  onLogin?: (role: AuthRole, username: string) => void
}

export function ChangePasswordPage({ onLogin }: ChangePasswordPageProps) {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const username = localStorage.getItem('username') ?? ''
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
      const response = await changePassword(username, currentPassword, newPassword, newPasswordConfirm)
      setMessage(response.message)
      if (response.success) {
        setCurrentPassword('')
        setNewPassword('')
        setNewPasswordConfirm('')

        if (forced) {
          const storedRole = localStorage.getItem('role')
          if (isAuthRole(storedRole)) {
            onLogin?.(storedRole, username)
            navigate(storedRole === 'admin' ? '/dashboard' : '/graph')
          }
        }
      }
    } catch {
      setMessage('Password change failed. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="grid min-h-full place-items-center p-6">
      <Card className="w-full max-w-[420px] bg-[color-mix(in_srgb,var(--background)_72%,transparent)]">
        <CardHeader>
          <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">Account</span>
          <CardTitle className="mt-2 text-[32px]">{forced ? 'Change password before continuing' : 'Change password'}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="grid gap-3.5">
            <Label>Current password<Input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required /></Label>
            <Label>New password<Input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required /></Label>
            <Label>Confirm new password<Input type="password" value={newPasswordConfirm} onChange={(event) => setNewPasswordConfirm(event.target.value)} required /></Label>
            {message && <p className="m-0 text-sm text-[var(--text-muted)]">{message}</p>}
            <Button type="submit" disabled={isSubmitting}>{isSubmitting ? 'Changing password...' : 'Change password'}</Button>
            {!forced && <Button type="button" variant="secondary" onClick={() => navigate(-1)}>Back</Button>}
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
