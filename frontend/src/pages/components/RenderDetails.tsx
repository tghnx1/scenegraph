import { Link } from 'react-router-dom'
import { Button } from '@/shared/ui/button'
import { cn } from '@/shared/lib/cn-utils'
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

const resultCardClass = 'rounded-[20px] border border-[var(--surface-border-soft)] bg-[var(--surface-panel-soft)] p-5'
const inlineResultCardClass = 'rounded-[18px] border border-[var(--surface-border)] bg-[var(--surface-panel)] p-4 shadow-none'
const resultHeaderClass = 'flex items-start justify-between gap-4'
const resultTypeClass = 'text-xs font-semibold uppercase tracking-[0.14em] text-[var(--accent)]'
const resultMetaClass = 'mt-1 text-sm text-[var(--text-muted)]'
const resultSectionClass = 'mt-5 grid gap-2.5'
const resultDescriptionClass = 'm-0 text-sm leading-6 text-[var(--text-muted)]'
const resultListClass = 'grid gap-2.5'
const resultTileClass = 'grid gap-1 rounded-xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-3 text-[var(--text)] no-underline transition-colors hover:border-[var(--selection-border)] hover:bg-[var(--selection-soft)]'
const resultPillClass = 'inline-flex items-center gap-2 rounded-full border border-[var(--control-border)] bg-[var(--control-bg)] px-3 py-1.5 text-sm font-semibold text-[var(--text)] no-underline transition-colors hover:border-[var(--selection-border)] hover:bg-[var(--selection-soft)]'
const resultSubheadingClass = 'm-0 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]'
const resultEmptyClass = 'text-sm text-[var(--text-muted)]'
const linkGroupClass = 'grid gap-4'
const pillsClass = 'flex flex-wrap gap-2'

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

export function ManualArtistConnectionButton({
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
    <div className="grid justify-items-start gap-1.5">
      <Button
        type="button"
        size="sm"
        variant={isConnected ? 'secondary' : 'outline'}
        className={cn(isConnected && 'border-[var(--selection-border)] bg-[var(--selection-soft)]')}
        onClick={() => void control.onToggle(artistId)}
        disabled={control.isLoading || control.pendingArtistId !== null}
      >
        {isPending
          ? (isConnected ? 'Removing...' : 'Adding...')
          : (isConnected ? 'Remove manual connection' : 'Add manual connection')}
      </Button>
      {control.error && <p className="m-0 text-sm text-[var(--event)]">{control.error}</p>}
    </div>
  )
}

export function RenderDetails({ result, variant = 'card', manualArtistConnections }: RenderDetailsProps) {
  const articleClassName = variant === 'inline' ? inlineResultCardClass : resultCardClass

  if (isArtistDetail(result)) {
    const linkedArtists = result.connected_artists
    const linkedEvents = result.events

    return (
      <article className={articleClassName}>
        <div className={resultHeaderClass}>
          <div>
            <span className={resultTypeClass}>Artist</span>
            <h2>{result.name}</h2>
            <p className={resultMetaClass}>{result.genres.join(' · ') || 'No genres yet'}</p>
          </div>
          <div className="flex shrink-0 items-start gap-2">
            <ManualArtistConnectionButton artistId={result.id} control={manualArtistConnections} />
          </div>
        </div>

        <section className={resultSectionClass}>
          <h3>Biography</h3>
          <p className={resultDescriptionClass}>{result.bio || 'No biography available yet.'}</p>
        </section>

        <section className={resultSectionClass}>
          <h3>Linked entities</h3>
          <div className={linkGroupClass}>
            <div>
              <p className={resultSubheadingClass}>Artists</p>
              <div className={pillsClass}>
                {linkedArtists.length > 0 ? (
                  linkedArtists.map((artist) => (
                    <Link
                      key={artist.id}
                      to={`/graph?selectedType=artist&selectedId=${encodeURIComponent(artist.id)}`}
                      className={resultPillClass}
                    >
                      {artist.name} <span>{artist.shared_events} shared</span>
                    </Link>
                  ))
                ) : (
                  <span className={resultEmptyClass}>No linked artists yet</span>
                )}
              </div>
            </div>

            <div>
              <p className={resultSubheadingClass}>Events</p>
              <div className={pillsClass}>
                {linkedEvents.length > 0 ? (
                  linkedEvents.map((event) => (
                    <Link
                      key={event.id}
                      to={`/graph?selectedType=event&selectedId=${encodeURIComponent(event.id)}`}
                      className={resultPillClass}
                    >
                      {event.title} <span>{dateOnly(event.event_date)}</span>
                    </Link>
                  ))
                ) : (
                  <span className={resultEmptyClass}>No linked events yet</span>
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
        <div className={resultHeaderClass}>
          <div>
            <span className={resultTypeClass}>Promoter</span>
            <h2>{result.name}</h2>
            <p className={resultMetaClass}>ID {result.id}</p>
          </div>
        </div>

        <section className={resultSectionClass}>
          <h3>Events</h3>
          <div className={resultListClass}>
            {result.events.map((event) => (
              <Link
                key={event.id}
                to={`/graph?selectedType=event&selectedId=${encodeURIComponent(event.id)}`}
                className={resultTileClass}
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
        <div className={resultHeaderClass}>
          <div>
            <span className={resultTypeClass}>Venue</span>
            <h2>{result.name}</h2>
            <p className={resultMetaClass}>{[result.address, result.district].filter(Boolean).join(' - ') || `ID ${result.id}`}</p>
          </div>
        </div>

        <section className={resultSectionClass}>
          <h3>Events</h3>
          <div className={resultListClass}>
            {result.events.map((event) => (
              <Link
                key={event.id}
                to={`/graph?selectedType=event&selectedId=${encodeURIComponent(event.id)}`}
                className={resultTileClass}
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
        <div className={resultHeaderClass}>
          <div>
            <span className={resultTypeClass}>Event</span>
            <h2>{result.title}</h2>
            <p className={resultMetaClass}>{dateOnly(result.date)}</p>
          </div>
        </div>

        <section className={resultSectionClass}>
          <h3>Linked entities</h3>
          <div className={linkGroupClass}>
            {result.venue && (
              <div>
                <p className={resultSubheadingClass}>Venue</p>
                <Link to={`/graph?selectedType=venue&selectedId=${encodeURIComponent(result.venue.id)}`} className={resultPillClass}>
                  {result.venue.name}
                </Link>
              </div>
            )}
            <div>
              <p className={resultSubheadingClass}>Artists</p>
              <div className={pillsClass}>
                {result.artists.map((artist) => (
                  <Link key={artist.id} to={`/graph?selectedType=artist&selectedId=${encodeURIComponent(artist.id)}`} className={resultPillClass}>
                    {artist.name}
                  </Link>
                ))}
              </div>
            </div>
            <div>
              <p className={resultSubheadingClass}>Promoters</p>
              <div className={pillsClass}>
                {result.promoters.map((promoter) => (
                  <Link key={promoter.id} to={`/graph?selectedType=promoter&selectedId=${encodeURIComponent(promoter.id)}`} className={resultPillClass}>
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
        <div className={resultHeaderClass}>
          <div>
            <span className={resultTypeClass}>Artist</span>
            <h2>{result.name}</h2>
            <p className={resultMetaClass}>{result.id}</p>
          </div>
          <ManualArtistConnectionButton artistId={result.id} control={manualArtistConnections} />
        </div>
      </article>
    )
  }

  if (result.type === 'venue') {
    return (
      <article className={articleClassName}>
        <div className={resultHeaderClass}>
          <div>
            <span className={resultTypeClass}>Venue</span>
            <h2>{result.name}</h2>
            <p className={resultMetaClass}>{result.id}</p>
          </div>
        </div>
      </article>
    )
  }

  if (result.type === 'promoter') {
    return (
      <article className={articleClassName}>
        <div className={resultHeaderClass}>
          <div>
            <span className={resultTypeClass}>Promoter</span>
            <h2>{result.name}</h2>
            <p className={resultMetaClass}>{result.id}</p>
          </div>
        </div>
      </article>
    )
  }

  return (
    <article className={articleClassName}>
      <div className={resultHeaderClass}>
        <div>
          <span className={resultTypeClass}>Event</span>
          <h2>{result.name}</h2>
          <p className={resultMetaClass}>{result.id}</p>
        </div>
      </div>
    </article>
  )
}
