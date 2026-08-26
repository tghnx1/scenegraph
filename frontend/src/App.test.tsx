import { MemoryRouter, useLocation } from 'react-router-dom'
import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const api = vi.hoisted(() => ({
  getMe: vi.fn(),
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

function CurrentLocation() {
  const location = useLocation()
  return <div data-testid="current-location">{location.pathname}{location.search}</div>
}

describe('App graph visibility', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getMe.mockResolvedValue({ profile_complete: true })
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

describe('App landing page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.getUiSettings.mockResolvedValue({ success: true, show_graph_tab: true })
    api.getMe.mockResolvedValue({ profile_complete: false })
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
      key: vi.fn(),
      length: 0,
    })
  })

  it('opens incomplete artist profiles at the profile workspace', async () => {
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key: string) => key === 'token' ? 'token' : key === 'role' ? 'artist' : null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
      key: vi.fn(),
      length: 2,
    })

    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
        <CurrentLocation />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Profile page')).toBeInTheDocument()
    expect(screen.getByTestId('current-location')).toHaveTextContent('/profile?workspace=profile')
  })

  it('opens complete artist profiles at the recommendations workspace', async () => {
    api.getMe.mockResolvedValue({ profile_complete: true })
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key: string) => {
        if (key === 'token') return 'token'
        if (key === 'role') return 'artist'
        if (key === 'profile_complete') return 'true'
        return null
      }),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
      key: vi.fn(),
      length: 3,
    })

    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
        <CurrentLocation />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Profile page')).toBeInTheDocument()
    expect(screen.getByTestId('current-location')).toHaveTextContent('/profile?workspace=recommendations')
  })

  it('shows the login page at the site root for unauthenticated visitors', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Login page')).toBeInTheDocument()
    expect(screen.queryByText('Graph page')).not.toBeInTheDocument()
  })
})
