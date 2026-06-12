import { Link } from 'react-router-dom'
import type { ArtistDetail } from '../../types/artist'
import type { EntityDetail } from '../../types/entityDetail'
import type { EventDetail } from '../../types/event'
import type { PromoterDetail } from '../../types/promoter'
import type { SearchResult } from '../../types/search'
import type { VenueDetail } from '../../types/venue'
import type { ManualArtistConnectionControl } from './DetailsPanel'

type RenderDetailsProps = {
  result: SearchResult | EntityDetail
  variant?: 'card' | 'inline'
  manualArtistConnections?: ManualArtistConnectionControl
}

type DisplayResult = SearchResult | EntityDetail

function isArtistDetail(result: DisplayResult): result is ArtistDetail {
  return result.type === 'artist' && 'connected_artists' in result
}

function isPromoterDetail(result: DisplayResult): result is PromoterDetail {
  return result.type === 'promoter' && 'events' in result
}

function isVenueDetail(result: DisplayResult): result is VenueDetail {
  return result.type === 'venue' && 'events' in result
}

function isEventDetail(result: DisplayResult): result is EventDetail {
  return result.type === 'event' && 'artists' in result
}

function dateOnly(date: string | null) {
  if (!date) return 'Date unavailable'
  return date.split(/[T ]/)[0]
}

function ManualArtistConnectionButton({
  artistId,
  control,
}: {
  artistId: number
  control?: ManualArtistConnectionControl
}) {
  if (!control || artistId === control.sourceArtistId) return null

  const isConnected = control.connectedArtistIds.has(artistId)
  const isPending = control.pendingArtistId === artistId

  return (
    <div className="manual-connection-action">
      <button
        type="button"
        className={isConnected ? 'manual-connection-button connected' : 'manual-connection-button'}
        onClick={() => void control.onToggle(artistId)}
        disabled={control.isLoading || control.pendingArtistId !== null}
      >
        {isPending
          ? (isConnected ? 'Removing...' : 'Adding...')
          : (isConnected ? 'Remove manual connection' : 'Add manual connection')}
      </button>
      {control.error && <p className="manual-connection-error">{control.error}</p>}
    </div>
  )
}

export function RenderDetails({ result, variant = 'card', manualArtistConnections }: RenderDetailsProps) {
  const articleClassName = variant === 'inline' ? 'search-result-card search-result-card--inline' : 'search-result-card'

  if (isArtistDetail(result)) {
    const linkedArtists = result.connected_artists
    const linkedEvents = result.events

    return (
      <article className={articleClassName}>
        <div className="result-header">
          <div>
            <span className="result-type">Artist</span>
            <h2>{result.name}</h2>
            <p className="result-meta">{result.genres.join(' · ') || 'No genres yet'}</p>
          </div>
          <div className="result-header-actions">
            <ManualArtistConnectionButton artistId={result.id} control={manualArtistConnections} />
          </div>
        </div>

        <section className="result-section">
          <h3>Biography</h3>
          <p className="result-description">{result.bio || 'No biography available yet.'}</p>
        </section>

        <section className="result-section">
          <h3>Linked entities</h3>
          <div className="result-link-groups">
            <div>
              <p className="result-subheading">Artists</p>
              <div className="result-pills compact">
                {linkedArtists.length > 0 ? (
                  linkedArtists.map((artist) => (
                    <Link
                      key={artist.id}
                      to={`/graph?selectedType=artist&selectedId=${encodeURIComponent(artist.id)}`}
                      className="result-pill"
                    >
                      {artist.name} <span>{artist.shared_events} shared</span>
                    </Link>
                  ))
                ) : (
                  <span className="result-empty-inline">No linked artists yet</span>
                )}
              </div>
            </div>

            <div>
              <p className="result-subheading">Events</p>
              <div className="result-pills compact">
                {linkedEvents.length > 0 ? (
                  linkedEvents.map((event) => (
                    <Link
                      key={event.id}
                      to={`/graph?selectedType=event&selectedId=${encodeURIComponent(event.id)}`}
                      className="result-pill"
                    >
                      {event.title} <span>{dateOnly(event.event_date)}</span>
                    </Link>
                  ))
                ) : (
                  <span className="result-empty-inline">No linked events yet</span>
                )}
              </div>
            </div>
          </div>
        </section>
      </article>
    )
  }

  if (isPromoterDetail(result)) {
    return (
      <article className={articleClassName}>
        <div className="result-header">
          <div>
            <span className="result-type">Promoter</span>
            <h2>{result.name}</h2>
            <p className="result-meta">ID {result.id}</p>
          </div>
        </div>

        <section className="result-section">
          <h3>Events</h3>
          <div className="result-list">
            {result.events.map((event) => (
              <Link
                key={event.id}
                to={`/graph?selectedType=event&selectedId=${encodeURIComponent(event.id)}`}
                className="result-tile"
              >
                <strong>{event.title}</strong>
                <span>{[event.date, event.venue_name].filter(Boolean).join(' - ')}</span>
                <span>{event.artists.join(', ') || 'No artists listed'}</span>
              </Link>
            ))}
          </div>
        </section>
      </article>
    )
  }

  if (isVenueDetail(result)) {
    return (
      <article className={articleClassName}>
        <div className="result-header">
          <div>
            <span className="result-type">Venue</span>
            <h2>{result.name}</h2>
            <p className="result-meta">{[result.address, result.district].filter(Boolean).join(' - ') || `ID ${result.id}`}</p>
          </div>
        </div>

        <section className="result-section">
          <h3>Events</h3>
          <div className="result-list">
            {result.events.map((event) => (
              <Link
                key={event.id}
                to={`/graph?selectedType=event&selectedId=${encodeURIComponent(event.id)}`}
                className="result-tile"
              >
                <strong>{event.title}</strong>
                <span>{event.date || 'Date unavailable'}</span>
                <span>{event.artists.join(', ') || 'No artists listed'}</span>
              </Link>
            ))}
          </div>
        </section>
      </article>
    )
  }

  if (isEventDetail(result)) {
    return (
      <article className={articleClassName}>
        <div className="result-header">
          <div>
            <span className="result-type">Event</span>
            <h2>{result.title}</h2>
            <p className="result-meta">{dateOnly(result.date)}</p>
          </div>
        </div>

        <section className="result-section">
          <h3>Linked entities</h3>
          <div className="result-link-groups">
            {result.venue && (
              <div>
                <p className="result-subheading">Venue</p>
                <Link to={`/graph?selectedType=venue&selectedId=${encodeURIComponent(result.venue.id)}`} className="result-pill">
                  {result.venue.name}
                </Link>
              </div>
            )}
            <div>
              <p className="result-subheading">Artists</p>
              <div className="result-pills compact">
                {result.artists.map((artist) => (
                  <Link key={artist.id} to={`/graph?selectedType=artist&selectedId=${encodeURIComponent(artist.id)}`} className="result-pill">
                    {artist.name}
                  </Link>
                ))}
              </div>
            </div>
            <div>
              <p className="result-subheading">Promoters</p>
              <div className="result-pills compact">
                {result.promoters.map((promoter) => (
                  <Link key={promoter.id} to={`/graph?selectedType=promoter&selectedId=${encodeURIComponent(promoter.id)}`} className="result-pill">
                    {promoter.name}
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </section>
      </article>
    )
  }

  if (result.type === 'artist') {
    return (
      <article className={articleClassName}>
        <div className="result-header">
          <div>
            <span className="result-type">Artist</span>
            <h2>{result.name}</h2>
            <p className="result-meta">{result.id}</p>
          </div>
          <ManualArtistConnectionButton artistId={result.id} control={manualArtistConnections} />
        </div>
      </article>
    )
  }

  if (result.type === 'venue') {
    return (
      <article className={articleClassName}>
        <div className="result-header">
          <div>
            <span className="result-type">Venue</span>
            <h2>{result.name}</h2>
            <p className="result-meta">{result.id}</p>
          </div>
        </div>
      </article>
    )
  }

  if (result.type === 'promoter') {
    return (
      <article className={articleClassName}>
        <div className="result-header">
          <div>
            <span className="result-type">Promoter</span>
            <h2>{result.name}</h2>
            <p className="result-meta">{result.id}</p>
          </div>
        </div>
      </article>
    )
  }

  return (
    <article className={articleClassName}>
      <div className="result-header">
        <div>
          <span className="result-type">Event</span>
          <h2>{result.name}</h2>
          <p className="result-meta">{result.id}</p>
        </div>
      </div>
    </article>
  )
}
