import {render, screen} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {describe, expect, it, vi} from 'vitest'
import {GraphNodeFilter} from './GraphNodeFilter'
import type {NodeType} from '../../types/graph'

describe('GraphNodeFilter', () => {
  it('renders interactive toggle buttons for the generic graph', async () => {
    const user = userEvent.setup()
    const onToggle = vi.fn()
    const visibleNodeTypes = new Set<NodeType>(['venue', 'artist', 'promoter', 'event'])

    render(
      <GraphNodeFilter
        visibleNodeTypes={visibleNodeTypes}
        onToggle={onToggle}
      />,
    )

    const venueButton = screen.getByRole('button', { name: 'Venue' })
    const artistButton = screen.getByRole('button', { name: 'Artist' })
    const promoterButton = screen.getByRole('button', { name: 'Promoter' })
    const eventButton = screen.getByRole('button', { name: 'Event' })

    expect(venueButton).toHaveAttribute('aria-pressed', 'true')
    expect(artistButton).toHaveAttribute('aria-pressed', 'true')
    expect(promoterButton).toHaveAttribute('aria-pressed', 'true')
    expect(eventButton).toBeDisabled()

    await user.click(artistButton)
    expect(onToggle).toHaveBeenCalledWith('artist')
  })
})
