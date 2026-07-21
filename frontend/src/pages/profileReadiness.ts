export type ArtistProfileReadiness = {
  isLoading: boolean
  hasBiography: boolean | null
  manualArtistCount: number
  requiredManualArtistCount: number
}

export function isArtistProfileReady(readiness: ArtistProfileReadiness | null | undefined): boolean {
  return Boolean(
    readiness
    && readiness.isLoading === false
    && readiness.hasBiography === true
    && readiness.manualArtistCount >= readiness.requiredManualArtistCount,
  )
}

export function getProfileSetupTargetId(readiness: Pick<ArtistProfileReadiness, 'hasBiography'>): 'artist-biography-panel' | 'artist-manual-connections' {
  return readiness.hasBiography === false ? 'artist-biography-panel' : 'artist-manual-connections'
}
