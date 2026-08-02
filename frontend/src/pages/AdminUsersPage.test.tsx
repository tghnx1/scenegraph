import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminUsersPage } from './AdminUsersPage'

const api = vi.hoisted(() => ({
    changeUserRole: vi.fn(),
    approveUser: vi.fn(),
    rejectUser: vi.fn(),
    getPendingUsers: vi.fn(),
    getUsers: vi.fn(),
    deactivateUser: vi.fn(),
    activateUser: vi.fn(),
    unbindArtist: vi.fn(),
  }))

vi.mock('../api/auth', () => api)

function installLocalStorageMock() {
  const store = new Map<string, string>()
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => {
        store.set(key, value)
      },
      removeItem: (key: string) => {
        store.delete(key)
      },
      clear: () => {
        store.clear()
      },
    },
  })
}

describe('AdminUsersPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    installLocalStorageMock()
  })

  it('renders the auto-approve toggle and approves pending users automatically when enabled', async () => {
    window.localStorage.setItem('scenegraph.admin.autoApprovePendingUsers', 'true')

    api.getPendingUsers
      .mockResolvedValueOnce({
        users: [
          {
            id: 101,
            username: 'friend-user',
            email: 'friend@example.com',
            role: 'artist',
            status: 'pending',
            created_at: '2026-08-02T10:00:00.000Z',
            artist_id: 33,
            artist_name: 'Friend Artist',
            artist_source: 'resident_advisor',
            artist_instagram_url: 'https://www.instagram.com/friendartist/',
            artist_content_url: '/events/33',
          },
        ],
      })
      .mockResolvedValueOnce({ users: [] })
    api.getUsers
      .mockResolvedValueOnce({ users: [] })
      .mockResolvedValueOnce({ users: [] })
    api.approveUser.mockResolvedValue({ success: true, message: 'User approved' })

    render(<AdminUsersPage />)

    expect(screen.getByRole('checkbox', { name: 'Auto-approve new registrations' })).toBeChecked()

    await waitFor(() => expect(api.approveUser).toHaveBeenCalledWith(101))
    await waitFor(() => expect(screen.queryByText('friend-user')).not.toBeInTheDocument())
  })

  it('renders an unbind artist action for linked users and calls the unbind endpoint', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    api.getPendingUsers.mockResolvedValue({ users: [] })
    api.getUsers.mockResolvedValue({
      users: [
        {
          id: 202,
          username: 'linked-user',
          email: 'linked@example.com',
          role: 'artist',
          status: 'approved',
          created_at: '2026-08-02T10:00:00.000Z',
          artist_id: 44,
          artist_name: 'Linked Artist',
          artist_source: 'resident_advisor',
          artist_instagram_url: 'https://www.instagram.com/linkedartist/',
          artist_content_url: '/events/44',
        },
      ],
    })
    api.unbindArtist.mockResolvedValue({ success: true, message: 'Artist unbound' })

    render(<AdminUsersPage />)

    const unbindButton = await screen.findByRole('button', { name: 'Unbind artist' })
    expect(unbindButton).toBeInTheDocument()

    await waitFor(() => expect(screen.getByText('linked-user')).toBeInTheDocument())
    await screen.findByText('Artist: Linked Artist')

    unbindButton.click()

    await waitFor(() => expect(api.unbindArtist).toHaveBeenCalledWith(202))
  })
})
