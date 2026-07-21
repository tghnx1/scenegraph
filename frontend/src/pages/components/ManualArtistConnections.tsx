import {useMemo, useState} from 'react'
import {Link} from 'react-router-dom'
import { Plus, Search, X } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { cn } from '@/shared/lib/cn-utils'
import { fetchSearch } from '@/api/search'
import { useApi } from '@/api/useApi'
import type {ManualArtistConnection} from '../../api/manualArtistConnections'
import type { SearchResponse, SearchResult } from '../../types/search'
import { useDebouncedValue } from '../hooks/useDebouncedValue'

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

export function ManualArtistConnections({
  connections,
  isLoading,
  pendingArtistId,
  error,
  onAdd,
  onRemove,
}: ManualArtistConnectionsProps) {
  const helperCopy = 'Add 3–5 artists you know, collaborate with, or who can recommend you to promoters.'
  const [isAddingOpen, setIsAddingOpen] = useState(false)
  const [searchValue, setSearchValue] = useState('')
  const debouncedSearchValue = useDebouncedValue(searchValue.trim(), 300)
  const shouldSearch = isAddingOpen && debouncedSearchValue.length >= 2
  const { data: searchData, isLoading: isSearchLoading, error: searchError } = useApi<SearchResponse>(
    () => (shouldSearch ? fetchSearch(debouncedSearchValue, 8, 'artist') : Promise.resolve(EMPTY_SEARCH_RESPONSE)),
    [debouncedSearchValue, shouldSearch],
  )

  const artistResults = useMemo(
    () => (searchData?.results ?? []).filter((result) => result.type === 'artist'),
    [searchData?.results],
  )

  const handleAddArtist = async (artistId: number) => {
    await onAdd(artistId)
    setSearchValue('')
  }

  return (
    <section
      id="artist-manual-connections"
      tabIndex={-1}
      className="scroll-mt-28 grid gap-4"
      aria-labelledby="manual-artist-connections-heading"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--surface-border-soft)] pb-2">
        <div className="grid gap-1">
          <h3 id="manual-artist-connections-heading">Artists you know</h3>
          <p className="m-0 text-sm text-[var(--text-muted)]">
            {helperCopy}
          </p>
        </div>
        {!isAddingOpen && connections.length > 0 && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setIsAddingOpen(true)}
          >
            Add artist
          </Button>
        )}
      </div>

      {isLoading && connections.length === 0 && !isAddingOpen ? (
        <p className="m-0 text-sm text-[var(--text-muted)]">Loading known artists...</p>
      ) : connections.length === 0 && !isAddingOpen ? (
        <button
          type="button"
          className="grid min-h-28 place-items-center rounded-2xl border border-dashed border-[var(--surface-border)] bg-[var(--surface-soft)] text-[var(--text-muted)] transition-colors hover:border-[var(--selection-border)] hover:bg-[var(--selection-soft)] hover:text-[var(--text)] focus-visible:border-[var(--selection-border)] focus-visible:bg-[var(--selection-soft)] focus-visible:text-[var(--text)] focus-visible:outline-none"
          onClick={() => setIsAddingOpen(true)}
          aria-label="Add artist"
        >
          <span className="inline-grid place-items-center gap-2">
            <span className="grid size-12 place-items-center rounded-full border border-[var(--surface-border-soft)] bg-[var(--surface-panel)]">
              <Plus className="size-6" aria-hidden="true" />
            </span>
            <span className="text-sm font-semibold">Add artist</span>
          </span>
        </button>
      ) : null}

      {isAddingOpen && (
        <section className="grid gap-3 rounded-2xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-4" aria-labelledby="artist-search-heading">
          <div className="flex items-center gap-2">
            <Search className="size-4 text-[var(--text-muted)]" aria-hidden="true" />
            <h4 id="artist-search-heading" className="m-0 text-sm font-semibold text-[var(--text)]">
              Search and add an artist
            </h4>
          </div>
          <label className="grid gap-2">
            <span className="sr-only">Search artists</span>
            <input
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

      {!isAddingOpen && connections.length > 0 && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-8">
          {connections.map((connection) => (
            <div className="relative" key={connection.connectedArtistId}>
              <Link
                to={`/graph?selectedType=artist&selectedId=${connection.connectedArtistId}`}
                className="grid min-h-full gap-1 rounded-xl border border-[var(--surface-border-soft)] bg-[var(--surface-soft)] p-3 pr-10 text-[var(--text)] no-underline transition-colors hover:border-[var(--selection-border)] hover:bg-[var(--selection-soft)]"
              >
                <strong>{connection.connectedArtistName}</strong>
                <span className="text-sm text-[var(--text-muted)]">Manual connection</span>
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
      )}
    </section>
  )
}
