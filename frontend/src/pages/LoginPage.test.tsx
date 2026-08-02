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
  await user.type(screen.getByLabelText(/Login username/i), 'friend-user')
  await user.type(screen.getByLabelText(/^Email$/i), 'friend@example.com')
  await user.type(screen.getByLabelText(/Instagram URL/i), 'https://www.instagram.com/frienduser/')
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
    expect(screen.getByText('Registration submitted. Your account will be available after manual review.')).toBeInTheDocument()
  })

  it('shows approved messaging when the backend returns an approved registration', async () => {
    const user = userEvent.setup()
    api.register.mockResolvedValue({
      success: true,
      message: 'Registration successful',
      user_id: 123,
      status: 'approved',
    })

    render(
      <MemoryRouter>
        <LoginPage onLogin={vi.fn()} />
      </MemoryRouter>,
    )

    await fillRegistrationForm(user)

    await waitFor(() => expect(api.register).toHaveBeenCalled())
    expect(screen.getByText('Registration approved. You can log in now.')).toBeInTheDocument()
  })
})
