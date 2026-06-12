import {useEffect, useState, type FormEvent} from 'react'
import {Link} from 'react-router-dom'
import {fetchArtistBiography, updateArtistBiography} from '../../api/entityDetails'
import type {ConnectedArtistItem} from '../../types/artist'
import {ManualArtistConnections} from './ManualArtistConnections'

interface BiographyPanelProps {
  artistId: number | null
  onConnectionsChange: () => void
}

export function BiographyPanel({artistId, onConnectionsChange}: BiographyPanelProps) {
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
    <article className="profile-card biography-panel">
      <div className="panel-heading">
        <div>
          <span className="search-query-label">Biography</span>
          <h2>{artistName}</h2>
        </div>
        {!isEditing && artistId !== null && !isLoading && (
          <button type="button" onClick={() => {
            setDraftBiography(biography)
            setSuccess(null)
            setIsEditing(true)
          }}>
            Edit Biography
          </button>
        )}
      </div>

      {isLoading ? (
        <p>Loading biography...</p>
      ) : isEditing ? (
        <form className="biography-form" onSubmit={handleSubmit}>
          <textarea
            value={draftBiography}
            onChange={(event) => setDraftBiography(event.target.value)}
            placeholder="Tell promoters and collaborators about your work, sound, and background."
            rows={10}
            maxLength={6000}
          />
          <div className="biography-form-footer">
            <span>{draftBiography.length}/6000</span>
            <div className="biography-form-actions">
              <button
                type="button"
                onClick={() => {
                  setDraftBiography(biography)
                  setError(null)
                  setIsEditing(false)
                }}
                disabled={isSaving}
              >
                Cancel
              </button>
              <button type="submit" disabled={isSaving || draftBiography === biography}>
                {isSaving ? 'Saving...' : 'Save biography'}
              </button>
            </div>
          </div>
        </form>
      ) : (
        <p className={biography ? 'biography-copy' : 'biography-empty'}>
          {biography || 'No biography added yet. Select Edit to introduce yourself.'}
        </p>
      )}

      {error && <p className="biography-message error">{error}</p>}
      {success && <p className="biography-message success">{success}</p>}

      {!isLoading && !error && (
        <section className="biography-linked-artists" aria-labelledby="biography-linked-artists-heading">
          <div className="biography-section-heading">
            <h3 id="biography-linked-artists-heading">Linked artists</h3>
            <span>{linkedArtists.length}</span>
          </div>
          <div className="biography-linked-artist-list">
            {linkedArtists.length > 0 ? linkedArtists.map((artist) => (
              <Link
                key={artist.id}
                to={`/graph?selectedType=artist&selectedId=${encodeURIComponent(artist.id)}`}
                className="biography-linked-artist"
              >
                <strong>{artist.name}</strong>
                <span>{artist.shared_events} shared event{artist.shared_events === 1 ? '' : 's'}</span>
              </Link>
            )) : (
              <p className="biography-empty">No linked artists yet.</p>
            )}
          </div>
        </section>
      )}

      {!isLoading && artistId !== null && (
        <ManualArtistConnections artistId={artistId} onConnectionsChange={onConnectionsChange} />
      )}
    </article>
  )
}
