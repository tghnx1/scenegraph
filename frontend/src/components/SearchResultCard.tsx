import { Link } from 'react-router-dom'
import type { SearchResult } from '../types/search'

type SearchResultCardProps = {
  result: SearchResult
  variant?: 'card' | 'inline'
}

export function SearchResultCard({ result, variant = 'card' }: SearchResultCardProps) {
  const articleClassName = variant === 'inline' ? 'search-result-card search-result-card--inline' : 'search-result-card'

  if (result.type === 'artist') {
    const linkedArtists = result.connectedArtists
    const linkedEvents = result.events

    return (
      <article className={articleClassName}>
        <div className="result-header">
          <div>
            <span className="result-type">Artist</span>
            <h2>{result.label}</h2>
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
                    <Link key={artist.id} to={`/graph?artist=${encodeURIComponent(artist.id)}`} className="result-pill">
                      {artist.label} <span>{artist.sharedEvents} shared</span>
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
                    <Link key={event.id} to={`/graph?q=${encodeURIComponent(event.label)}`} className="result-pill">
                      {event.label} <span>{event.date}</span>
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

  if (result.type === 'venue') {
    return (
      <article className={articleClassName}>
        <div className="result-header">
          <div>
            <span className="result-type">Venue</span>
            <h2>{result.label}</h2>
            <p className="result-meta">
              {result.address ?? 'Address not provided'}
              {result.district ? ` · ${result.district}` : ''}
            </p>
          </div>
          <span className="result-badge">{result.eventCount} events</span>
        </div>

        <section className="result-section">
          <h3>Events conducted here</h3>
          <div className="result-list">
            {result.events.map((event) => (
              <div key={event.id} className="result-tile">
                <strong>{event.label}</strong>
                <span>{event.date}</span>
                <span>{event.artists.join(' · ')}</span>
                <span>{event.promoters.join(' · ')}</span>
              </div>
            ))}
          </div>
        </section>
      </article>
    )
  }

  if (result.type === 'promoter') {
    return (
      <article className={articleClassName}>
        <div className="result-header">
          <div>
            <span className="result-type">Promoter</span>
            <h2>{result.label}</h2>
          </div>
          <span className="result-badge">{result.eventCount} events</span>
        </div>

        <section className="result-section">
          <h3>Events organized</h3>
          <div className="result-list">
            {result.events.map((event) => (
              <div key={event.id} className="result-tile">
                <strong>{event.label}</strong>
                <span>{event.date}</span>
                <span>{event.venueName}</span>
                <span>{event.artists.join(' · ')}</span>
              </div>
            ))}
          </div>
        </section>
      </article>
    )
  }

  return (
    <article className={articleClassName}>
      <div className="result-header">
        <div>
          <span className="result-type">Event</span>
          <h2>{result.label}</h2>
          <p className="result-meta">{result.date}</p>
        </div>
        <span className="result-badge">Live event</span>
      </div>

      <section className="result-section">
        <h3>Venue</h3>
        <p className="result-description">{result.venue.label}</p>
      </section>

      <section className="result-section two-column">
        <div>
          <h3>Artists</h3>
          <div className="result-pills compact">
            {result.artists.map((artist) => (
              <Link key={artist.id} to={`/graph?artist=${encodeURIComponent(artist.id)}`} className="result-pill">
                {artist.label}
              </Link>
            ))}
          </div>
        </div>
        <div>
          <h3>Promoters</h3>
          <div className="result-pills compact">
            {result.promoters.map((promoter) => (
              <span key={promoter.id} className="result-pill muted">
                {promoter.label}
              </span>
            ))}
          </div>
        </div>
      </section>
    </article>
  )
}