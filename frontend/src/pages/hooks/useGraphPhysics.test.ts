import { describe, expect, it } from 'vitest'
import { getDisconnectedNodeIds, getDisconnectedNodeTargetRadius } from './useGraphPhysics'

describe('getDisconnectedNodeIds', () => {
  it('returns only nodes that are not connected to the center component', () => {
    const disconnected = getDisconnectedNodeIds(
      [{ id: 'center' }, { id: 'connected-a' }, { id: 'connected-b' }, { id: 'isolated' }],
      [
        { source: 'center', target: 'connected-a' },
        { source: 'connected-a', target: 'connected-b' },
      ],
      'center',
    )

    expect(disconnected).toEqual(new Set(['isolated']))
  })

  it('returns an empty set when the center node is missing', () => {
    const disconnected = getDisconnectedNodeIds(
      [{ id: 'a' }, { id: 'b' }],
      [{ source: 'a', target: 'b' }],
      'center',
    )

    expect(disconnected).toEqual(new Set())
  })
})

describe('getDisconnectedNodeTargetRadius', () => {
  it('returns the target radius for disconnected nodes', () => {
    expect(getDisconnectedNodeTargetRadius('isolated', new Set(['isolated']))).toBe(95)
  })

  it('returns zero for connected nodes', () => {
    expect(getDisconnectedNodeTargetRadius('connected', new Set(['isolated']))).toBe(0)
  })
})
