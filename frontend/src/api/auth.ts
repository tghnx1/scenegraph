import { api } from './client'

export type AuthRole = 'user' | 'admin'

export interface LoginResponse {
  success: boolean
  message: string
  user_id?: number
  username?: string
  access_token?: string
}

export interface RegisterResponse {
  success: boolean
  message: string
  user_id?: number
}

export const login = (username: string, password: string): Promise<LoginResponse> =>
  api.post<LoginResponse>('/login', { username, password })

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

export const getFallbackRole = (username: string): AuthRole => (
  username.trim().toLowerCase() === 'aaron' ? 'admin' : 'user'
)
