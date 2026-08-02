import { describe, expect, it } from 'vitest'
import {
  getIsolatedNodeIds,
  getIsolatedNodeTargetPosition,
  getIsolatedNodeTargetRadius,
} from './useGraphPhysics'

describe('getIsolatedNodeIds', () => {
  it('returns only nodes that have no links at all', () => {
    const isolated = getIsolatedNodeIds(
      [{ id: 'center' }, { id: 'connected-a' }, { id: 'connected-b' }, { id: 'isolated' }],
      [
        { source: 'center', target: 'connected-a' },
        { source: 'connected-a', target: 'connected-b' },
      ],
    )

    expect(isolated).toEqual(new Set(['isolated']))
  })

  it('returns every node when there are no links', () => {
    const isolated = getIsolatedNodeIds(
      [{ id: 'a' }, { id: 'b' }],
      [],
    )

    expect(isolated).toEqual(new Set(['a', 'b']))
  })

  it('returns an empty set when every node participates in at least one link', () => {
    const isolated = getIsolatedNodeIds(
      [{ id: 'a' }, { id: 'b' }],
      [{ source: 'a', target: 'b' }],
    )

    expect(isolated).toEqual(new Set())
  })
})

describe('getIsolatedNodeTargetRadius', () => {
  it('returns the target radius for isolated nodes', () => {
    expect(getIsolatedNodeTargetRadius('isolated', new Set(['isolated']))).toBe(30)
  })

  it('returns zero for connected nodes', () => {
    expect(getIsolatedNodeTargetRadius('connected', new Set(['isolated']))).toBe(0)
  })
})

describe('getIsolatedNodeTargetPosition', () => {
  it('assigns different isolated nodes to different target positions', () => {
    const isolatedIds = new Set(['alpha', 'beta'])

    expect(getIsolatedNodeTargetPosition('alpha', isolatedIds)).not.toEqual(
      getIsolatedNodeTargetPosition('beta', isolatedIds),
    )
  })

  it('returns null for connected nodes', () => {
    expect(getIsolatedNodeTargetPosition('connected', new Set(['isolated']))).toBeNull()
  })
})
