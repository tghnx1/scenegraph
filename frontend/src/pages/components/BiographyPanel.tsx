import {useEffect, useState, type FormEvent} from 'react'
import {Link} from 'react-router-dom'
import { Button } from '@/shared/ui/button'
import { BIOGRAPHY_MAX_LENGTH, validateBiography } from '@/shared/lib/validation'
import {fetchArtistBiography, updateArtistBiography} from '../../api/entityDetails'
import type {ConnectedArtistItem} from '../../types/artist'
import {ManualArtistConnections, type ManualArtistConnectionsProps} from './ManualArtistConnections'

interface BiographyPanelProps {
  artistId: number | null
  manualConnections: ManualArtistConnectionsProps
}

export function BiographyPanel({artistId, manualConnections}: BiographyPanelProps) {
  const [artistName, setArtistName] = useState('Artist profile')
  const [biography, setBiography] = useState('')
  const [draftBiography, setDraftBiography] = useState('')
  const [linkedArtists, setLinkedArtists] = useState<ConnectedArtistItem[]>([])
  const [isEditing, setIsEditing] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  useEffect(() => {
    let isCurrent = true

    if (artistId === null) {
      setIsLoading(false)
      setError('This account is not linked to an artist profile yet.')
      return () => { isCurrent = false }
    }

    setIsLoading(true)
    setError(null)
    fetchArtistBiography(artistId)
      .then((artist) => {
        if (!isCurrent) return
        const nextBiography = artist.bio ?? ''
        setArtistName(artist.name)
        setBiography(nextBiography)
        setDraftBiography(nextBiography)
        setLinkedArtists(artist.connected_artists)
      })
      .catch((requestError) => {
        if (!isCurrent) return
        setError(requestError instanceof Error ? requestError.message : 'Failed to load biography.')
      })
      .finally(() => {
        if (isCurrent) setIsLoading(false)
      })

    return () => { isCurrent = false }
  }, [artistId])

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
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Failed to save biography.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <article className="grid gap-4 rounded-3xl border border-[color-mix(in_srgb,var(--text)_10%,transparent)] bg-[color-mix(in_srgb,var(--background)_42%,transparent)] p-5 shadow-[0_10px_24px_rgba(0,0,0,0.12)] backdrop-blur-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">Biography</span>
          <h2>{artistName}</h2>
        </div>
        {!isEditing && artistId !== null && !isLoading && (
          <Button type="button" size="sm" onClick={() => {
            setDraftBiography(biography)
            setSuccess(null)
            setIsEditing(true)
          }}>
            Edit Biography
          </Button>
        )}
      </div>

      {isLoading ? (
        <p>Loading biography...</p>
      ) : isEditing ? (
        <form className="grid gap-3" onSubmit={handleSubmit}>
          <textarea
            className="min-h-64 w-full resize-y rounded-xl border border-[var(--control-border)] bg-[var(--surface-input)] p-3 text-sm text-[var(--text)] outline-none placeholder:text-[var(--text-placeholder)] focus:border-[var(--focus-border)] focus:shadow-[0_0_0_3px_var(--focus-ring)]"
            value={draftBiography}
            onChange={(event) => setDraftBiography(event.target.value)}
            placeholder="Tell promoters and collaborators about your work, sound, and background."
            rows={10}
            maxLength={BIOGRAPHY_MAX_LENGTH}
          />
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
      ) : (
        <p className={biography ? 'm-0 whitespace-pre-wrap text-sm leading-6 text-[var(--text)]' : 'm-0 text-sm text-[var(--text-muted)]'}>
          {biography || 'No biography added yet. Select Edit to introduce yourself.'}
        </p>
      )}

      {error && <p className="m-0 rounded-xl border border-[var(--event-border-soft)] bg-[var(--event-soft)] p-3 text-sm text-[var(--event)]">{error}</p>}
      {success && <p className="m-0 rounded-xl border border-[var(--promoter-border)] bg-[var(--promoter-soft)] p-3 text-sm text-[var(--text)]">{success}</p>}

      {!isLoading && !error && (
        <section className="grid gap-3" aria-labelledby="biography-linked-artists-heading">
          <div className="flex items-center justify-between gap-3 border-b border-[var(--surface-border-soft)] pb-2">
            <h3 id="biography-linked-artists-heading">Linked artists</h3>
          </div>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-2">
            {linkedArtists.length > 0 ? linkedArtists.map((artist) => (
              <Link
                key={artist.id}
                to={`/graph?selectedType=artist&selectedId=${encodeURIComponent(artist.id)}`}
                className="grid gap-1 rounded-xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-3 text-[var(--text)] no-underline transition-colors hover:border-[var(--selection-border)] hover:bg-[var(--selection-soft)]"
              >
                <strong>{artist.name}</strong>
                <span className="text-sm text-[var(--text-muted)]">{artist.shared_events} shared event{artist.shared_events === 1 ? '' : 's'}</span>
              </Link>
            )) : (
              <p className="m-0 text-sm text-[var(--text-muted)]">No linked artists yet.</p>
            )}
          </div>
        </section>
      )}

      {!isLoading && artistId !== null && (
        <ManualArtistConnections {...manualConnections} />
      )}
    </article>
  )
}
