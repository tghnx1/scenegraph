import { api } from './client'

export type AuthRole = 'user' | 'contributor' | 'admin'

export const isAuthRole = (value: unknown): value is AuthRole =>
  value === 'user' || value === 'contributor' || value === 'admin'

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
  api.get('/admin/users/pending', {
    headers: { 'X-Admin-Username': localStorage.getItem('username') ?? '' },
  })

export const approveUser = (userId: number): Promise<{ success: boolean; message: string }> =>
  api.post(`/admin/users/${userId}/approve`, undefined, {
    headers: { 'X-Admin-Username': localStorage.getItem('username') ?? '' },
  })

export const rejectUser = (
  userId: number,
): Promise<{ success: boolean; message: string }> =>
  api.post(`/admin/users/${userId}/reject`, undefined, {
    headers: {
      'X-Admin-Username': localStorage.getItem('username') ?? '',
    },
  })

export interface RegisterResponse {
  success: boolean
  message: string
  user_id?: number
}

export const register = (
  username: string,
  email: string,
  password: string,
  password_confirm: string
): Promise<RegisterResponse> =>
  api.post<RegisterResponse>('/register', {
    username,
    email,
    password,
    password_confirm,
  })

export interface ActivityLogItem {
  id: number
  username: string | null
  event_type: string
  target: string | null
  created_at: string
}

export const getActivityLog = (): Promise<{ success: boolean; activity: ActivityLogItem[] }> =>
  api.get('/admin/activity', {
    headers: { 'X-Admin-Username': localStorage.getItem('username') ?? ''},
  })

export const logout = (
  username: string,
): Promise<{ success: boolean; message: string }> =>
  api.post('/logout', { username, password: '' })

export interface UserItem {
  id: number
  username: string
  email: string
  role: AuthRole
  status: string
  created_at: string
}

export const getUsers = (): Promise<{ success: boolean; users: UserItem[] }> =>
  api.get('/admin/users', {
    headers: { 'X-Admin-Username': localStorage.getItem('username') ?? '' },
  })

export const deactivateUser = (
  userId: number,
): Promise<{ success: boolean; message: string }> =>
  api.post(`/admin/users/${userId}/deactivate`, undefined, {
    headers: { 'X-Admin-Username': localStorage.getItem('username') ?? '' },
  })
