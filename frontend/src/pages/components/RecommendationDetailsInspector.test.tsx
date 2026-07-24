import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { EntityDetail } from '../../types/entityDetail'
import type { GraphNode } from '../../types/graph'
import { RecommendationDetailsInspector } from './RecommendationDetailsInspector'

vi.mock('./RenderDetails', () => ({
  RenderDetails: () => <div data-testid="render-details" />,
}))

describe('RecommendationDetailsInspector', () => {
  it('keeps the outer header compact and leaves the entity title to the details card', () => {
    const selectedNode: GraphNode = {
      id: 'promoter-42',
      entityId: 42,
      type: 'promoter',
      name: 'Good Day Berlin Kultur und Veranstaltungen GmbH',
      genres: [],
    }
    const selectedEntityDetail = {
      type: 'promoter',
      id: 42,
      name: 'Good Day Berlin Kultur und Veranstaltungen GmbH',
      events: [],
    } as EntityDetail

    render(
      <RecommendationDetailsInspector
        selectedNode={selectedNode}
        selectedEntityDetail={selectedEntityDetail}
        isLoading={false}
        error={null}
        onSelectNode={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByLabelText('Recommendation details')).toBeInTheDocument()
    expect(screen.getByRole('button', {name: 'Close'})).toBeInTheDocument()
    expect(screen.queryByRole('heading', {name: selectedNode.name})).not.toBeInTheDocument()
    expect(screen.queryByText(selectedNode.type)).not.toBeInTheDocument()
    expect(screen.getByTestId('render-details')).toBeInTheDocument()
  })
})
