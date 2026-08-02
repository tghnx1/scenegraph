import { describe, expect, it } from 'vitest'
import { getNodeDisplaySize } from './drawNode'

describe('getNodeDisplaySize', () => {
  it('shrinks isolated nodes by half', () => {
    expect(getNodeDisplaySize(5, 0)).toBe(2.5)
  })

  it('shrinks leaf nodes by half', () => {
    expect(getNodeDisplaySize(5, 1)).toBe(2.5)
  })

  it('keeps connected nodes at the base size', () => {
    expect(getNodeDisplaySize(5, 2)).toBe(5)
  })
})
