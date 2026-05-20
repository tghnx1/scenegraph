import { Link } from 'react-router-dom'
import type { Artist } from '../../types/artist'
import type { SearchResult } from '../../types/search'

type SearchResultCardProps = {
  result: SearchResult | Artist
  variant?: 'card' | 'inline'
}

function isArtistDetail(result: SearchResult | Artist): result is Artist {
  return result.type === 'artist' && 'connectedArtists' in result
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
                    <Link key={artist.id} to={`/graph?artist=${encodeURIComponent(artist.id)}`} className="result-pill">
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
                    <Link key={event.id} to={`/graph?q=${encodeURIComponent(event.title)}`} className="result-pill">
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
