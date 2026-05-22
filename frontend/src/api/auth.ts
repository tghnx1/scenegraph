import { api } from './client'

export type AuthRole = 'user' | 'admin'

export interface LoginResponse {
  success: boolean
  message: string
  user_id?: number
  username?: string
  access_token?: string
}

export const login = (username: string, password: string): Promise<LoginResponse> =>
  api.post<LoginResponse>('/login', { username, password })

export const getFallbackRole = (username: string): AuthRole => (
  username.trim().toLowerCase() === 'aaron' ? 'admin' : 'user'
)
