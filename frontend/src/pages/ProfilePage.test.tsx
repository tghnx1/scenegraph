import type { FormEvent } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ProfilePage } from './ProfilePage'

const graphPanelMock = vi.hoisted(() => vi.fn(() => <div data-testid="graph-panel" />))
const recommendationPanelMock = vi.hoisted(() => vi.fn(() => <div data-testid="recommendations-panel" />))
const detailsPanelMock = vi.hoisted(() => vi.fn(({ selectedNode, selectedEntityDetail }: { selectedNode: { name: string } | null; selectedEntityDetail: { name: string } | null }) => (
  <div data-testid="details-panel">
    <span>{selectedEntityDetail?.name ?? selectedNode?.name ?? 'empty'}</span>
  </div>
)))
const biographyPanelMock = vi.hoisted(() => vi.fn(() => <div data-testid="biography-panel" />))
const manualConnectionsMock = vi.hoisted(() => vi.fn(() => ({
  connections: [],
  connectedArtistIds: new Set<number>(),
  isLoading: false,
  pendingArtistId: null,
  error: null,
  add: vi.fn(),
  remove: vi.fn(),
  toggle: vi.fn(),
})))

vi.mock('./hooks/useManualArtistConnections.ts', () => ({
  useManualArtistConnections: manualConnectionsMock,
}))
vi.mock('./components/SearchInputField.tsx', () => ({
  SearchInputField: ({ value, onChange, onSubmit, onClear }: {
    value: string
    onChange: (value: string) => void
    onSubmit: (event: FormEvent<HTMLFormElement>) => void
    onClear: () => void
  }) => (
    <form onSubmit={onSubmit}>
      <label>
        Search Database
        <input
          aria-label="Search Database"
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      </label>
      <button type="button" onClick={onClear}>Clear search</button>
    </form>
  ),
}))
vi.mock('./components/DetailsPanel.tsx', () => ({ DetailsPanel: detailsPanelMock }))
vi.mock('./components/GraphPanel.tsx', () => ({ ScenegraphMapPanel: graphPanelMock }))
vi.mock('./components/RecommendationPanel.tsx', () => ({
  PromoterRecommendationsPanel: recommendationPanelMock,
}))
vi.mock('./components/BiographyPanel.tsx', () => ({ BiographyPanel: biographyPanelMock }))
vi.mock('../api/auth', () => ({
  getMe: vi.fn(async () => ({
    role: 'artist',
    artist_id: null,
    artist_name: null,
  })),
}))
vi.mock('../api/entityDetails', () => ({
  fetchEntityDetail: vi.fn(async (_type: string, id: string) => ({
    id: Number(id),
    type: 'artist',
    name: 'Selected Artist',
  })),
}))
vi.mock('../api/search', () => ({
  SEARCH_RESULT_LIMIT: 10,
  SEARCH_RESULT_MAX_LIMIT: 100,
  fetchSearch: vi.fn(async (query: string) => ({ query, results: [] })),
}))

describe('ProfilePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
      key: vi.fn(),
      length: 0,
    })
  })

  it('keeps the Graph sidebar and hides it on Recommendations', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/profile?q=holy&selectedType=artist&selectedId=61']}>
        <ProfilePage showBiography={false} />
      </MemoryRouter>,
    )

    expect(await screen.findByTestId('recommendations-panel')).toBeInTheDocument()
    expect(screen.queryByLabelText('Search Database')).not.toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Graph' }))

    expect(screen.getByLabelText('Search Database')).toHaveValue('holy')
    expect(screen.getByTestId('details-panel')).toHaveTextContent('Selected Artist')
    expect(screen.getByTestId('recommendations-panel')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Recommendations' }))

    expect(screen.queryByLabelText('Search Database')).not.toBeInTheDocument()
    expect(screen.queryByTestId('details-panel')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Promoter recommendations workspace')).toHaveClass('col-span-full')
    expect(screen.getByTestId('recommendations-panel')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Graph' }))

    expect(screen.getByLabelText('Search Database')).toHaveValue('holy')
    expect(screen.getByTestId('details-panel')).toHaveTextContent('Selected Artist')
  })

  it('preserves the search query when switching tabs', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter initialEntries={['/profile?q=holy']}>
        <ProfilePage showBiography={false} />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('tab', { name: 'Graph' }))

    const input = screen.getByLabelText('Search Database')
    expect(input).toHaveValue('holy')

    await user.clear(input)
    await user.type(input, 'strobe')
    expect(input).toHaveValue('strobe')

    await user.click(screen.getByRole('tab', { name: 'Recommendations' }))
    await user.click(screen.getByRole('tab', { name: 'Graph' }))

    expect(screen.getByLabelText('Search Database')).toHaveValue('strobe')
  })

  it('opens a contextual recommendation drawer without restoring the global sidebar', async () => {
    const user = userEvent.setup()
    const recommendationNode = {
      id: 'promoter-99',
      type: 'promoter',
      entityId: 99,
      name: 'Suggested Promoter',
      genres: [],
    }

    recommendationPanelMock.mockImplementation(({ onSelectNode }: { onSelectNode: (node: unknown) => void }) => (
      <div>
        <button type="button" onClick={() => onSelectNode(recommendationNode)}>Select recommendation</button>
      </div>
    ))

    render(
      <MemoryRouter initialEntries={['/profile']}>
        <ProfilePage showBiography={false} />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole('tab', { name: 'Recommendations' }))
    await user.click(screen.getByRole('button', { name: 'Select recommendation' }))

    expect(screen.getByRole('dialog', { name: 'Suggested Promoter' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Search Database')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Close' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Suggested Promoter' })).not.toBeInTheDocument())
  })
})
