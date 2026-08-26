import { MemoryRouter } from 'react-router-dom'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LoginPage } from './LoginPage'

const api = vi.hoisted(() => ({
  login: vi.fn(),
  register: vi.fn(),
}))

vi.mock('../api/auth', () => api)
vi.mock('../api/search', () => ({
  SEARCH_RESULT_LIMIT: 10,
  fetchSearch: vi.fn(async () => ({ query: '', results: [] })),
}))

function createStorageMock() {
  const store = new Map<string, string>()
  return {
    getItem: vi.fn((key: string) => store.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store.set(key, String(value))
    }),
    removeItem: vi.fn((key: string) => {
      store.delete(key)
    }),
    clear: vi.fn(() => {
      store.clear()
    }),
  }
}

async function fillRegistrationForm(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: 'Create account' }))
  await user.type(screen.getByLabelText(/^Email$/i), 'friend@example.com')
  await user.type(screen.getByLabelText(/Artist profile search/i), 'Friend Artist')

  await user.click(await screen.findByRole('button', { name: /Create new artist "Friend Artist"/i }))

  const [passwordInput] = screen.getAllByLabelText(/^Password$/i)
  await user.type(passwordInput, 'Password123')
  await user.type(screen.getByLabelText(/^Confirm password$/i), 'Password123')
  await user.click(screen.getByRole('button', { name: 'Register' }))
}

describe('LoginPage registration status messaging', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('localStorage', createStorageMock())
    vi.stubGlobal('sessionStorage', createStorageMock())
  })

  it('signs in with email instead of a username', async () => {
    const user = userEvent.setup()
    api.login.mockResolvedValue({
      success: true,
      message: 'Login successful',
      username: 'friend@example.com',
      role: 'artist',
      access_token: 'test-token',
    })

    render(
      <MemoryRouter>
        <LoginPage onLogin={vi.fn()} />
      </MemoryRouter>,
    )

    await user.type(screen.getByLabelText(/^Email$/i), 'FRIEND@EXAMPLE.COM')
    await user.type(screen.getByLabelText(/^Password$/i), 'Password123')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => expect(api.login).toHaveBeenCalledWith('friend@example.com', 'Password123'))
  })

  it('shows manual review messaging when the backend returns a pending registration', async () => {
    const user = userEvent.setup()
    api.register.mockResolvedValue({
      success: true,
      message: 'Registration successful',
      user_id: 123,
      status: 'pending',
    })

    render(
      <MemoryRouter>
        <LoginPage onLogin={vi.fn()} />
      </MemoryRouter>,
    )

    await fillRegistrationForm(user)

    await waitFor(() => expect(api.register).toHaveBeenCalled())
    expect(api.register).toHaveBeenCalledWith(expect.objectContaining({ email: 'friend@example.com' }))
    expect(api.register.mock.calls[0][0]).not.toHaveProperty('username')
    expect(api.register.mock.calls[0][0]).not.toHaveProperty('instagram_url')
    expect(screen.queryByLabelText(/Login username/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/Instagram URL/i)).not.toBeInTheDocument()
    expect(screen.getByText('Registration submitted. Your account will be available after manual review.')).toBeInTheDocument()
  })

  it('signs in immediately when registration is auto-approved', async () => {
    const user = userEvent.setup()
    const onLogin = vi.fn()
    api.register.mockResolvedValue({
      success: true,
      message: 'Registration successful',
      user_id: 123,
      status: 'approved',
      username: 'friend@example.com',
      role: 'artist',
      artist_id: 44,
      access_token: 'registration-token',
      profile_complete: false,
    })

    render(
      <MemoryRouter>
        <LoginPage onLogin={onLogin} />
      </MemoryRouter>,
    )

    await fillRegistrationForm(user)

    await waitFor(() => expect(api.register).toHaveBeenCalled())
    expect(onLogin).toHaveBeenCalledWith('artist', true, false)
    expect(localStorage.setItem).toHaveBeenCalledWith('token', 'registration-token')
  })
})
