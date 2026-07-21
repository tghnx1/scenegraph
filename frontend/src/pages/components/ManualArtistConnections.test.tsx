import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ManualArtistConnections } from './ManualArtistConnections'

const baseProps = {
  isLoading: false,
  pendingArtistId: null,
  error: null,
  onAdd: vi.fn(),
  onRemove: vi.fn(),
}

describe('ManualArtistConnections', () => {
  it('shows one empty-state add button and no duplicate helper controls', () => {
    render(
      <ManualArtistConnections
        {...baseProps}
        connections={[]}
      />,
    )

    expect(screen.getByText('Artists you know')).toBeInTheDocument()
    expect(screen.getByText('Add 3–5 artists you know, collaborate with, or who can recommend you to promoters.')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Add artist' })).toHaveLength(1)
    expect(screen.queryByLabelText('Explain how to add artists')).not.toBeInTheDocument()
    expect(screen.queryByText('No artists added yet.')).not.toBeInTheDocument()
  })

  it('shows a header add button when connections already exist and hides the empty dashed button', () => {
    render(
      <ManualArtistConnections
        {...baseProps}
        connections={[
          {
            sourceArtistId: 61,
            connectedArtistId: 77,
            connectedArtistName: 'Neon Duo',
            createdAt: '2026-07-21T10:00:00.000Z',
            updatedAt: '2026-07-21T10:00:00.000Z',
          },
        ]}
      />,
    )

    expect(screen.getAllByRole('button', { name: 'Add artist' })).toHaveLength(1)
    expect(screen.getByText('Neon Duo')).toBeInTheDocument()
    expect(screen.queryByText('No artists added yet.')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Add artist' }))

    expect(screen.getByRole('heading', { name: 'Search and add an artist' })).toBeInTheDocument()
    expect(screen.queryAllByRole('button', { name: 'Add artist' })).toHaveLength(0)
  })
})
