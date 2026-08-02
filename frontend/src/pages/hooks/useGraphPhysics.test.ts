import { describe, expect, it } from 'vitest'
import { getLeafRadialTargetRadius } from './useGraphPhysics'

describe('getLeafRadialTargetRadius', () => {
  it('returns the target radius for low-degree nodes', () => {
    expect(getLeafRadialTargetRadius('node-a', new Set(['node-a']))).toBe(150)
  })

  it('returns zero for connected nodes', () => {
    expect(getLeafRadialTargetRadius('node-b', new Set(['node-a']))).toBe(0)
  })

  it('returns zero when no node id is provided', () => {
    expect(getLeafRadialTargetRadius(null, new Set(['node-a']))).toBe(0)
  })
})
