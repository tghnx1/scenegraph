import { describe, expect, it } from 'vitest'
import { getProfileSetupTargetId, isArtistProfileReady, type ArtistProfileReadiness } from './profileReadiness'

describe('profile readiness helpers', () => {
  it('treats the profile as ready only when biography and manual connections are complete', () => {
    const ready: ArtistProfileReadiness = {
      isLoading: false,
      hasBiography: true,
      manualArtistCount: 3,
      requiredManualArtistCount: 3,
    }

    expect(isArtistProfileReady(ready)).toBe(true)
    expect(isArtistProfileReady({ ...ready, hasBiography: false })).toBe(false)
    expect(isArtistProfileReady({ ...ready, manualArtistCount: 2 })).toBe(false)
    expect(isArtistProfileReady({ ...ready, isLoading: true })).toBe(false)
    expect(isArtistProfileReady(null)).toBe(false)
  })

  it('targets biography first when it is missing, otherwise manual connections', () => {
    expect(getProfileSetupTargetId({ hasBiography: false })).toBe('artist-biography-panel')
    expect(getProfileSetupTargetId({ hasBiography: true })).toBe('artist-manual-connections')
    expect(getProfileSetupTargetId({ hasBiography: null })).toBe('artist-manual-connections')
  })
})
