import {useCallback, useEffect, useMemo, useState, type FormEvent} from 'react'
import {Link} from 'react-router-dom'
import {Button} from '@/shared/ui/button'
import {BIOGRAPHY_MAX_LENGTH, validateBiography} from '@/shared/lib/validation'
import {fetchArtistBiography, updateArtistBiography} from '../../api/entityDetails'
import type {ConnectedArtistItem} from '../../types/artist'
import {ManualArtistConnections, type ManualArtistConnectionsProps} from './ManualArtistConnections'
import {RecommendationSignalsHelp} from './RecommendationSignalsHelp'

interface BiographyPanelProps {
  artistId: number | null
  selectedArtistName?: string | null
  manualConnections: ManualArtistConnectionsProps
  canEditBiography: boolean
  hasApprovedArtistProfile: boolean
  onBiographyStatusChange?: (status: { isLoading: boolean; hasBiography: boolean | null }) => void
  onProfileChanged?: () => void
}

const BIOGRAPHY_HELPER_CHIPS = [
  'Styles and genres',
  'DJ, producer or live-act roles',
  'Labels and imprints',
  'Collectives or crews',
  'Named residencies',
  'A clear description of your sound',
] as const

export function BiographyPanel({
  artistId,
  selectedArtistName,
  manualConnections,
  canEditBiography,
  hasApprovedArtistProfile,
  onBiographyStatusChange,
  onProfileChanged,
}: BiographyPanelProps) {
  const [artistName, setArtistName] = useState('Artist profile')
  const [biography, setBiography] = useState('')
  const [draftBiography, setDraftBiography] = useState('')
  const [linkedArtists, setLinkedArtists] = useState<ConnectedArtistItem[]>([])
  const [isEditing, setIsEditing] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const hasArtistProfileTarget = artistId !== null
  const shouldShowApprovedProfileWorkspace = hasApprovedArtistProfile && hasArtistProfileTarget
  const reportBiographyStatus = useCallback((status: { isLoading: boolean; hasBiography: boolean | null }) => {
    onBiographyStatusChange?.(status)
  }, [onBiographyStatusChange])

  useEffect(() => {
    let isCurrent = true

    if (artistId === null || !hasApprovedArtistProfile) {
      setIsLoading(false)
      setArtistName(selectedArtistName ?? 'Artist profile')
      setBiography('')
      setDraftBiography('')
      setLinkedArtists([])
      setIsEditing(false)
      setSuccess(null)
      setError(null)
      reportBiographyStatus({ isLoading: false, hasBiography: null })
      return () => { isCurrent = false }
    }

    setIsLoading(true)
    setError(null)
    reportBiographyStatus({ isLoading: true, hasBiography: null })
    fetchArtistBiography(artistId)
      .then((artist) => {
        if (!isCurrent) return
        const nextBiography = artist.bio ?? ''
        setArtistName(artist.name)
        setBiography(nextBiography)
        setDraftBiography(nextBiography)
        setLinkedArtists(artist.connected_artists)
        reportBiographyStatus({
          isLoading: false,
          hasBiography: nextBiography.trim().length > 0,
        })
      })
      .catch((requestError) => {
        if (!isCurrent) return
        const message = requestError instanceof Error
          ? requestError.message.replace(/^400:\s*/, '').replace(/^409:\s*/, '')
          : 'Failed to load biography.'
        setError(message)
        reportBiographyStatus({ isLoading: false, hasBiography: null })
      })
      .finally(() => {
        if (isCurrent) setIsLoading(false)
      })

    return () => { isCurrent = false }
  }, [artistId, hasApprovedArtistProfile, onProfileChanged, reportBiographyStatus, selectedArtistName])

  const showShortBiographyHint = useMemo(() => {
    const draftLength = draftBiography.trim().length
    return draftLength > 0 && draftLength < 160
  }, [draftBiography])
  const biographyHasContent = biography.trim().length > 0
  const biographyActionLabel = biographyHasContent ? 'Edit biography' : 'Add biography'

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (artistId === null) return

    setIsSaving(true)
    setError(null)
    setSuccess(null)
    const validationError = validateBiography(draftBiography)
    if (validationError) {
      setError(validationError)
      setIsSaving(false)
      return
    }

    try {
      const response = await updateArtistBiography(artistId, draftBiography)
      setBiography(response.biography)
      setDraftBiography(response.biography)
      setIsEditing(false)
      setSuccess('Biography saved.')
      onProfileChanged?.()
      reportBiographyStatus({
        isLoading: false,
        hasBiography: response.biography.trim().length > 0,
      })
    } catch (requestError) {
      const message = requestError instanceof Error
        ? requestError.message.replace(/^400:\s*/, '').replace(/^409:\s*/, '')
        : 'Failed to save biography.'
      setError(message)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <article
      id="artist-biography-panel"
      tabIndex={-1}
      className="scroll-mt-28 grid gap-5 rounded-3xl border border-[color-mix(in_srgb,var(--text)_10%,transparent)] bg-[color-mix(in_srgb,var(--background)_42%,transparent)] p-5 shadow-[0_10px_24px_rgba(0,0,0,0.12)] backdrop-blur-sm md:gap-6 md:p-6"
    >
      <div className="grid gap-1">
        <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">Artist profile</span>
        <h2>{artistName}</h2>
      </div>

      <RecommendationSignalsHelp />

      <section className="grid gap-4 rounded-2xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-4 md:gap-3 md:p-5">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="m-0">Biography</h3>
          {canEditBiography && artistId !== null && !isLoading && !isEditing && (
            <Button
              type="button"
              size="sm"
              onClick={() => {
                setDraftBiography(biography)
                setError(null)
                setSuccess(null)
                setIsEditing(true)
              }}
            >
              {biographyActionLabel}
            </Button>
          )}
        </header>

        {isLoading ? (
          <p className="m-0 text-sm text-[var(--text-muted)]">Loading biography...</p>
        ) : isEditing ? (
          <form className="grid gap-3" onSubmit={handleSubmit}>
            <textarea
              className="min-h-64 w-full resize-y rounded-xl border border-[var(--control-border)] bg-[var(--surface-input)] p-3 text-sm text-[var(--text)] outline-none placeholder:text-[var(--text-placeholder)] focus:border-[var(--focus-border)] focus:shadow-[0_0_0_3px_var(--focus-ring)]"
              value={draftBiography}
              onChange={(event) => setDraftBiography(event.target.value)}
              placeholder="Describe your sound and scene. Mention your styles, roles, labels, collectives, residencies, and relevant artistic background."
              rows={10}
              maxLength={BIOGRAPHY_MAX_LENGTH}
            />
            <div className="flex flex-wrap gap-2">
              {BIOGRAPHY_HELPER_CHIPS.map((chip) => (
                <span
                  key={chip}
                  className="rounded-full border border-[var(--surface-border-soft)] bg-[var(--surface-panel)] px-3 py-1 text-xs font-medium text-[var(--text-muted)]"
                >
                  {chip}
                </span>
              ))}
            </div>
            {showShortBiographyHint && (
              <p className="m-0 rounded-xl border border-[var(--info-border)] bg-[var(--info-soft)] p-3 text-sm text-[var(--text)]">
                Your bio is quite short. A few specific sentences will give recommendations more useful context.
              </p>
            )}
            <div className="flex items-center justify-between gap-3 text-sm text-[var(--text-muted)]">
              <span>{draftBiography.length}/{BIOGRAPHY_MAX_LENGTH}</span>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setDraftBiography(biography)
                    setError(null)
                    setIsEditing(false)
                  }}
                  disabled={isSaving}
                >
                  Cancel
                </Button>
                <Button type="submit" size="sm" disabled={isSaving || draftBiography === biography}>
                  {isSaving ? 'Saving...' : 'Save biography'}
                </Button>
              </div>
            </div>
          </form>
        ) : shouldShowApprovedProfileWorkspace ? (
          <>
            {biography ? (
              <p className="m-0 whitespace-pre-wrap text-sm leading-6 text-[var(--text)]">
                {biography}
              </p>
            ) : (
              <div className="grid gap-2 rounded-2xl border border-[var(--surface-border-soft)] bg-[var(--surface-panel)] p-4">
                <p className="m-0 text-sm text-[var(--text-muted)]">No biography added yet.</p>
                <p className="m-0 text-sm leading-6 text-[var(--text-muted)]">
                  Describe your sound, styles, roles, labels, collectives and residencies.
                </p>
              </div>
            )}
          </>
        ) : null}

        {error && (
          <p className="m-0 whitespace-pre-line rounded-xl border border-[var(--event-border-soft)] bg-[var(--event-soft)] p-3 text-sm text-[var(--event)]">
            {error}
          </p>
        )}
        {success && <p className="m-0 rounded-xl border border-[var(--promoter-border)] bg-[var(--promoter-soft)] p-3 text-sm text-[var(--text)]">{success}</p>}
      </section>

      {!isLoading && shouldShowApprovedProfileWorkspace && linkedArtists.length > 0 && (
        <section className="grid gap-4 rounded-2xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-4 md:gap-3 md:p-5" aria-labelledby="biography-linked-artists-heading">
          <div className="flex items-center justify-between gap-3 border-b border-[var(--surface-border-soft)] pb-2">
            <h3 id="biography-linked-artists-heading">Linked artists</h3>
          </div>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-2">
            {linkedArtists.map((artist) => (
              <Link
                key={artist.id}
                to={`/graph?selectedType=artist&selectedId=${encodeURIComponent(artist.id)}`}
                className="grid gap-1 rounded-xl border border-[var(--surface-border-soft)] bg-[var(--surface-panel)] p-3 text-[var(--text)] no-underline transition-colors hover:border-[var(--selection-border)] hover:bg-[var(--selection-soft)]"
              >
                <strong>{artist.name}</strong>
                <span className="text-sm text-[var(--text-muted)]">
                  {artist.shared_events} shared event{artist.shared_events === 1 ? '' : 's'}
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {!isLoading && shouldShowApprovedProfileWorkspace && canEditBiography && (
        <ManualArtistConnections {...manualConnections} onAdd={manualConnections.onAdd} />
      )}
    </article>
  )
}
