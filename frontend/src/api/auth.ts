import { api } from './client'

export type AuthRole = 'user' | 'admin'

export interface LoginResponse {
  success: boolean
  message: string
  user_id?: number
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

//export const getFallbackRole = (username: string): AuthRole => (
//  username.trim().toLowerCase() === 'aaron' ? 'admin' : 'user'
//)  the backend already knows the role.

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
