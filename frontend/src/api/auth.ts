import { api } from './client'

export type AuthRole = 'artist' | 'agent' | 'admin'

export interface LoginResponse {
  success: boolean
  message: string
  user_id?: number
  artist_id?: number
  username?: string
  role?: AuthRole
  access_token?: string
  must_change_password?: boolean
}
export interface ChangePasswordResponse {
  success: boolean
  message: string
}

export const changePassword = (
  username: string,
  current_password: string,
  new_password: string,
  new_password_confirm: string,
): Promise<ChangePasswordResponse> =>
  api.post<ChangePasswordResponse>('/change-password', {
    username,
    current_password,
    new_password,
    new_password_confirm,
  })

export const login = (username: string, password: string): Promise<LoginResponse> =>
  api.post<LoginResponse>('/login', { username, password })

export interface PendingUser {
  id: number
  username: string
  email: string
  role: AuthRole
  status: string
  created_at: string
}

export const getPendingUsers = (): Promise<{ success: boolean; users: PendingUser[] }> =>
  api.get('/admin/users/pending')

export const approveUser = (userId: number): Promise<{ success: boolean; message: string }> =>
  api.post(`/admin/users/${userId}/approve`, undefined)

export const rejectUser = (
  userId: number,
): Promise<{ success: boolean; message: string }> =>
  api.post(`/admin/users/${userId}/reject`, undefined)

export interface RegisterResponse {
  success: boolean
  message: string
  user_id?: number
}

export const register = (
  username: string,
  email: string,
  password: string,
  password_confirm: string,
  role: 'artist' | 'agent',
): Promise<RegisterResponse> =>
  api.post<RegisterResponse>('/register', {
    username,
    email,
    password,
    password_confirm,
    role,
  })

export interface ActivityLogItem {
  id: number
  username: string | null
  event_type: string
  target: string | null
  created_at: string
}

export const getActivityLog = (): Promise<{ success: boolean; activity: ActivityLogItem[] }> =>
  api.get('/admin/activity')

export const exportActivityLog = async (): Promise<void> => {
  const token = localStorage.getItem('token')

  const response = await fetch('/api/admin/activity/export', {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })

  if (!response.ok) {
    throw new Error('Export failed')
  }

  const text = await response.text()
  const blob = new Blob([text], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)

  const link = document.createElement('a')
  link.href = url
  link.download = 'activity_log.txt'
  link.click()

  URL.revokeObjectURL(url)
}

export const logout = (): Promise<{ success: boolean; message: string }> =>
  api.post('/logout', undefined)
export interface UserItem {
  id: number
  username: string
  email: string
  role: AuthRole
  status: string
  created_at: string
}

export const getUsers = (): Promise<{ success: boolean; users: UserItem[] }> =>
  api.get('/admin/users')

export const deactivateUser = (
  userId: number,
): Promise<{ success: boolean; message: string }> =>
  api.post(`/admin/users/${userId}/deactivate`, undefined)

export const activateUser = (
  userId: number,
): Promise<{ success: boolean; message: string }> =>
  api.post(`/admin/users/${userId}/activate`, undefined)

export const changeUserRole = (
  userId: number,
  role: 'artist' | 'agent',
): Promise<{ success: boolean; message: string }> =>
  api.post(`/admin/users/${userId}/role`, { role })
