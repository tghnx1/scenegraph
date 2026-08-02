import { describe, expect, it } from 'vitest'
import { getNodeCenteringStrength } from './useGraphPhysics'

describe('getNodeCenteringStrength', () => {
  it('uses stronger centering for low-degree nodes', () => {
    expect(getNodeCenteringStrength('node-a', new Set(['node-a']))).toBe(0.12)
  })

  it('keeps normal centering for connected nodes', () => {
    expect(getNodeCenteringStrength('node-b', new Set(['node-a']))).toBe(0.04)
  })

  it('keeps normal centering when no node id is provided', () => {
    expect(getNodeCenteringStrength(null, new Set(['node-a']))).toBe(0.04)
  })
})
