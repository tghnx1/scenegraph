import { Link } from 'react-router-dom'
import type { Artist } from '../../types/artist'
import type { EntityDetail } from '../../types/entityDetail'
import type { EventDetail } from '../../types/event'
import type { PromoterDetail } from '../../types/promoter'
import type { SearchResult } from '../../types/search'
import type { VenueDetail } from '../../types/venue'

type SearchResultCardProps = {
  result: SearchResult | Artist | EntityDetail
  variant?: 'card' | 'inline'
}

type DisplayResult = SearchResult | Artist | EntityDetail

function isArtistDetail(result: DisplayResult): result is Artist {
  return result.type === 'artist' && 'connectedArtists' in result
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

export function SearchResultCard({ result, variant = 'card' }: SearchResultCardProps) {
  const articleClassName = variant === 'inline' ? 'search-result-card search-result-card--inline' : 'search-result-card'

  if (isArtistDetail(result)) {
    const linkedArtists = result.connectedArtists
    const linkedEvents = result.events

    return (
      <article className={articleClassName}>
        <div className="result-header">
          <div>
            <span className="result-type">Artist</span>
            <h2>{result.name}</h2>
            <p className="result-meta">{result.genres.join(' · ') || 'No genres yet'}</p>
          </div>
          <span className="result-badge">{result.eventCount} events</span>
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
                      {artist.name} <span>{artist.shared_events_count} shared</span>
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
                      {event.title} <span>{event.date}</span>
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
          <span className="result-badge">{result.event_count} events</span>
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
          <span className="result-badge">{result.event_count} events</span>
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
            <p className="result-meta">{result.date || 'Date unavailable'}</p>
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
