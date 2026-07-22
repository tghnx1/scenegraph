import {useMemo, useRef, useState} from 'react'
import {Link} from 'react-router-dom'
import {Plus, Search, X} from 'lucide-react'
import {cn} from '@/shared/lib/cn-utils'
import {Button} from '@/shared/ui/button'
import {fetchSearch} from '@/api/search'
import {useApi} from '@/api/useApi'
import type {ManualArtistConnection} from '../../api/manualArtistConnections'
import type {SearchResponse, SearchResult} from '../../types/search'
import {useDebouncedValue} from '../hooks/useDebouncedValue'

export interface ManualArtistConnectionsProps {
  connections: ManualArtistConnection[]
  isLoading: boolean
  pendingArtistId: number | null
  error: string | null
  onAdd: (connectedArtistId: number) => Promise<void>
  onRemove: (connectedArtistId: number) => Promise<void>
}

const EMPTY_SEARCH_RESPONSE: SearchResponse = { query: '', results: [] }

function normalizeSnippet(value: string, maxLength = 120) {
  const normalized = value.replace(/\s+/g, ' ').trim()
  if (!normalized) return ''
  if (normalized.length <= maxLength) return normalized
  return `${normalized.slice(0, maxLength - 1).trimEnd()}…`
}

function artistResultMeta(result: SearchResult) {
  const bioSnippet = normalizeSnippet(result.biography_normalized ?? result.biography_preview ?? '')
  if (bioSnippet) return bioSnippet

  const details: string[] = []
  if (result.genres?.length) details.push(result.genres.slice(0, 3).join(' · '))
  if (result.latest_event_title) details.push(`Latest event: ${result.latest_event_title}`)
  return details.join(' • ')
}

function connectionProgressCopy(connectionCount: number) {
  if (connectionCount <= 0) {
    return 'Add at least 3 relevant artists to unlock recommendations.'
  }

  if (connectionCount < 3) {
    return `Add ${3 - connectionCount} more to unlock recommendations.`
  }

  if (connectionCount < 5) {
    return 'Recommendations are unlocked. Adding more relevant artists can broaden your network.'
  }

  return `Strong network context: ${connectionCount} artists added.`
}

export function ManualArtistConnections({
  connections,
  isLoading,
  pendingArtistId,
  error,
  onAdd,
  onRemove,
}: ManualArtistConnectionsProps) {
  const helperCopy = 'Add artists you genuinely know, have played with, collaborated with, or who could recommend you.'
  const [isAddingOpen, setIsAddingOpen] = useState(false)
  const [searchValue, setSearchValue] = useState('')
  const searchInputRef = useRef<HTMLInputElement | null>(null)
  const debouncedSearchValue = useDebouncedValue(searchValue.trim(), 300)
  const shouldSearch = isAddingOpen && debouncedSearchValue.length >= 2

  const {data: searchData, isLoading: isSearchLoading, error: searchError} = useApi<SearchResponse>(
    () => (shouldSearch ? fetchSearch(debouncedSearchValue, 8, 'artist') : Promise.resolve(EMPTY_SEARCH_RESPONSE)),
    [debouncedSearchValue, shouldSearch],
  )

  const artistResults = useMemo(
    () => (searchData?.results ?? []).filter((result) => result.type === 'artist'),
    [searchData?.results],
  )

  const focusSearchInput = () => {
    window.requestAnimationFrame(() => {
      searchInputRef.current?.focus()
    })
  }

  const openSearch = () => {
    if (!isAddingOpen) {
      setIsAddingOpen(true)
      focusSearchInput()
      return
    }

    searchInputRef.current?.focus()
  }

  const handleCloseSearch = () => {
    setIsAddingOpen(false)
    setSearchValue('')
  }

  const handleAddArtist = async (artistId: number) => {
    await onAdd(artistId)
    setSearchValue('')
    focusSearchInput()
  }

  return (
    <section
      id="artist-manual-connections"
      tabIndex={-1}
      className="grid gap-4 rounded-2xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-4 scroll-mt-28 md:gap-5 md:p-5"
      aria-labelledby="manual-artist-connections-heading"
    >
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-[var(--surface-border-soft)] pb-2">
        <div className="grid gap-1">
          <h3 id="manual-artist-connections-heading">Artists you know</h3>
          <p className="m-0 text-sm text-[var(--text-muted)]">
            {helperCopy}
          </p>
          <p className="m-0 text-sm text-[var(--text-muted)]">
            More relevant connections can broaden your matches.
          </p>
        </div>
        <div className="grid justify-items-end gap-1">
          <span className="rounded-full border border-[var(--surface-border-soft)] bg-[var(--surface-panel)] px-3 py-1 text-xs font-semibold text-[var(--text-muted)]">
            {connections.length} added
          </span>
          <span className="max-w-[16rem] text-right text-xs leading-5 text-[var(--text-muted)]">
            {connectionProgressCopy(connections.length)}
          </span>
        </div>
      </header>

      <div
        data-testid="manual-artist-connections-grid"
        className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-8"
      >
        <button
          type="button"
          className={cn(
            'grid h-full min-h-[110px] place-content-center gap-2 rounded-xl border border-dashed border-[var(--surface-border-soft)] bg-[var(--surface-panel)] p-3 text-center text-[var(--text-muted)] transition-colors hover:border-[var(--selection-border)] hover:bg-[var(--selection-soft)] hover:text-[var(--text)] focus-visible:border-[var(--selection-border)] focus-visible:bg-[var(--selection-soft)] focus-visible:text-[var(--text)] focus-visible:outline-none',
            isAddingOpen && 'border-[var(--selection-border)] bg-[var(--selection-soft)] text-[var(--text)]',
            isLoading && 'pointer-events-none opacity-80',
          )}
          onClick={openSearch}
          aria-label="Add artists"
          aria-expanded={isAddingOpen}
          aria-controls="manual-artist-search-panel"
          disabled={isLoading}
        >
          <span className="mx-auto inline-grid place-items-center gap-2">
            <span className="grid size-12 place-items-center rounded-full border border-[var(--surface-border-soft)] bg-[var(--surface-soft)]">
              <Plus className="size-7" aria-hidden="true" />
            </span>
            <span className="text-sm font-semibold">Add artists</span>
          </span>
        </button>

        {connections.map((connection) => (
          <div className="relative" key={connection.connectedArtistId}>
            <Link
              to={`/graph?selectedType=artist&selectedId=${connection.connectedArtistId}`}
              className="grid h-full min-h-[110px] place-content-center gap-1 rounded-xl border border-[var(--surface-border-soft)] bg-[var(--surface-panel)] p-3 pr-10 text-[var(--text)] no-underline transition-colors hover:border-[var(--selection-border)] hover:bg-[var(--selection-soft)]"
            >
              <strong className="text-balance">{connection.connectedArtistName}</strong>
              <span className="sr-only">Manual connection</span>
            </Link>
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="absolute right-2 top-2 size-7 rounded-full"
              onClick={() => void onRemove(connection.connectedArtistId)}
              disabled={pendingArtistId === connection.connectedArtistId}
              aria-label={`Remove ${connection.connectedArtistName} from manual connections`}
              title={pendingArtistId === connection.connectedArtistId ? 'Removing...' : 'Remove connection'}
            >
              <X aria-hidden="true" />
            </Button>
          </div>
        ))}
      </div>

      {isLoading ? (
        <p className="m-0 text-sm text-[var(--text-muted)]">
          {connections.length === 0 ? 'Loading known artists...' : 'Updating artists...'}
        </p>
      ) : null}

      {isAddingOpen && (
        <section
          id="manual-artist-search-panel"
          className="grid gap-3 rounded-2xl border border-[var(--surface-border-soft)] bg-[var(--surface-panel)] p-4"
          aria-labelledby="artist-search-heading"
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Search className="size-4 text-[var(--text-muted)]" aria-hidden="true" />
              <h4 id="artist-search-heading" className="m-0 text-sm font-semibold text-[var(--text)]">
                Search and add an artist
              </h4>
            </div>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={handleCloseSearch}
            >
              Done
            </Button>
          </div>
          <label className="grid gap-2">
            <span className="sr-only">Search artists</span>
            <input
              ref={searchInputRef}
              className="w-full rounded-xl border border-[var(--control-border)] bg-[var(--surface-input)] px-3 py-2.5 text-sm text-[var(--text)] outline-none placeholder:text-[var(--text-placeholder)] focus:border-[var(--focus-border)] focus:shadow-[0_0_0_3px_var(--focus-ring)]"
              type="search"
              value={searchValue}
              onChange={(event) => setSearchValue(event.target.value)}
              placeholder="Search artist name..."
              autoComplete="off"
              spellCheck={false}
            />
          </label>

          {searchValue.trim().length < 2 ? (
            <p className="m-0 text-sm text-[var(--text-muted)]">
              Start typing to find an artist, then add them to your profile.
            </p>
          ) : isSearchLoading ? (
            <p className="m-0 text-sm text-[var(--text-muted)]">Searching artists...</p>
          ) : searchError ? (
            <p className="m-0 rounded-xl border border-[var(--event-border-soft)] bg-[var(--event-soft)] p-3 text-sm text-[var(--event)]">
              {searchError}
            </p>
          ) : artistResults.length > 0 ? (
            <div className="grid gap-2">
              {artistResults.map((artist) => {
                const isPending = pendingArtistId === artist.id
                const isAlreadyAdded = connections.some((connection) => connection.connectedArtistId === artist.id)
                return (
                  <button
                    key={artist.id}
                    type="button"
                    className={cn(
                      'grid gap-2 rounded-2xl border border-[var(--surface-border-soft)] bg-[var(--surface-panel)] p-3 text-left transition-colors hover:border-[var(--selection-border)] hover:bg-[var(--selection-soft)]',
                      isAlreadyAdded && 'opacity-80',
                    )}
                    onClick={() => void handleAddArtist(artist.id)}
                    disabled={isPending || isAlreadyAdded}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="grid gap-1">
                        <strong className="text-[var(--text)]">{artist.name}</strong>
                        <span className="text-sm text-[var(--text-muted)]">
                          {artistResultMeta(artist) || 'Artist profile'}
                        </span>
                      </div>
                      <span className="rounded-full border border-[var(--control-border)] bg-[var(--control-bg)] px-2 py-0.5 text-xs font-semibold text-[var(--text)]">
                        {isAlreadyAdded ? 'Added' : isPending ? 'Adding…' : 'Add'}
                      </span>
                    </div>
                  </button>
                )
              })}
            </div>
          ) : (
            <p className="m-0 text-sm text-[var(--text-muted)]">No artist matches yet.</p>
          )}
        </section>
      )}

      {error && <p className="m-0 rounded-xl border border-[var(--event-border-soft)] bg-[var(--event-soft)] p-3 text-sm text-[var(--event)]">{error}</p>}
    </section>
  )
}
