import {render, screen} from '@testing-library/react'
import {describe, expect, it} from 'vitest'
import {GraphNodeLegend} from './GraphNodeLegend'

describe('GraphNodeLegend', () => {
  it('renders a static node-type legend without interactive controls', () => {
    render(<GraphNodeLegend />)

    expect(screen.getByLabelText('Graph node type legend')).toBeInTheDocument()
    expect(screen.getByText('Node types')).toBeInTheDocument()
    expect(screen.getByText('Venue')).toBeInTheDocument()
    expect(screen.getByText('Artist')).toBeInTheDocument()
    expect(screen.getByText('Promoter')).toBeInTheDocument()
    expect(screen.getByText('Event')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
