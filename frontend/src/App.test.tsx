import { MemoryRouter } from 'react-router-dom'
import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const api = vi.hoisted(() => ({
  getUiSettings: vi.fn(),
  logout: vi.fn(),
}))

vi.mock('./api/auth', () => api)
vi.mock('./pages/GraphPage', () => ({ GraphPage: () => <div>Graph page</div> }))
vi.mock('./pages/DashboardPage', () => ({ DashboardPage: () => <div>Dashboard page</div> }))
vi.mock('./pages/ProfilePage', () => ({ ProfilePage: () => <div>Profile page</div> }))
vi.mock('./pages/AgencyPage', () => ({ AgencyPage: () => <div>Agency page</div> }))
vi.mock('./pages/LoginPage', () => ({ LoginPage: () => <div>Login page</div> }))
vi.mock('./pages/ChangePasswordPage', () => ({ ChangePasswordPage: () => <div>Change password page</div> }))
vi.mock('./pages/AboutPage', () => ({ AboutPage: () => <div>About page</div> }))
vi.mock('./shared/styles/colors', () => ({
  applyTheme: vi.fn(),
  getStoredTheme: vi.fn(() => 'dark'),
}))

describe('App graph visibility', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key: string) => {
        if (key === 'token') return 'token'
        if (key === 'role') return 'admin'
        if (key === 'username') return 'admin-user'
        return null
      }),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
      key: vi.fn(),
      length: 3,
    })
  })

  it('hides the Graph nav entry when the ui setting disables it', async () => {
    api.getUiSettings.mockResolvedValue({ success: true, show_graph_tab: false })

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <App />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.queryByRole('link', { name: 'Graph' })).not.toBeInTheDocument())
    expect(screen.getByText('Dashboard page')).toBeInTheDocument()
  })
})
