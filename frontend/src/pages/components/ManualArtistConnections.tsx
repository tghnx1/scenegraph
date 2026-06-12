import {useCallback, useEffect, useMemo, useState, type FormEvent} from 'react'
import {Link} from 'react-router-dom'
import {
  addKnownArtist,
  listKnownArtists,
  removeKnownArtist,
  type ManualArtistConnection,
} from '../../api/manualArtistConnections'
import {SEARCH_RESULT_LIMIT, SEARCH_RESULT_MAX_LIMIT, fetchSearch} from '../../api/search'
import type {SearchResult} from '../../types/search'
import {useDebouncedValue} from '../hooks/useDebouncedValue'
import {SearchInputField} from './SearchInputField'

interface ManualArtistConnectionsProps {
  artistId: number
  onConnectionsChange: () => void
}

export function ManualArtistConnections({artistId, onConnectionsChange}: ManualArtistConnectionsProps) {
  const [connections, setConnections] = useState<ManualArtistConnection[]>([])
  const [searchValue, setSearchValue] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [searchLimit, setSearchLimit] = useState(SEARCH_RESULT_LIMIT)
  const [rawSearchResultCount, setRawSearchResultCount] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [isSearching, setIsSearching] = useState(false)
  const [pendingArtistId, setPendingArtistId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const debouncedSearchValue = useDebouncedValue(searchValue.trim(), 300)
  const connectedIds = useMemo(
    () => new Set(connections.map((connection) => connection.connectedArtistId)),
    [connections],
  )

  const loadConnections = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await listKnownArtists(artistId)
      setConnections(response.items)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Failed to load known artists.')
    } finally {
      setIsLoading(false)
    }
  }, [artistId])

  useEffect(() => {
    void loadConnections()
  }, [loadConnections])

  useEffect(() => {
    setSearchLimit(SEARCH_RESULT_LIMIT)
  }, [debouncedSearchValue])

  useEffect(() => {
    let isCurrent = true

    if (debouncedSearchValue.length < 2) {
      setSearchResults([])
      setRawSearchResultCount(0)
      setIsSearching(false)
      return () => { isCurrent = false }
    }

    setIsSearching(true)
    fetchSearch(debouncedSearchValue, searchLimit, 'artist')
      .then((response) => {
        if (!isCurrent) return
        setRawSearchResultCount(response.results.length)
        setSearchResults(response.results.filter((result) => (
          result.type === 'artist'
          && result.id !== artistId
          && !connectedIds.has(result.id)
        )))
      })
      .catch((requestError) => {
        if (isCurrent) setError(requestError instanceof Error ? requestError.message : 'Artist search failed.')
      })
      .finally(() => {
        if (isCurrent) setIsSearching(false)
      })

    return () => { isCurrent = false }
  }, [artistId, connectedIds, debouncedSearchValue, searchLimit])

  const canLoadMoreSearchResults =
    debouncedSearchValue.length >= 2
    && !isSearching
    && searchLimit < SEARCH_RESULT_MAX_LIMIT
    && rawSearchResultCount >= searchLimit

  const handleAdd = async (result: SearchResult) => {
    if (result.type !== 'artist') return
    setPendingArtistId(result.id)
    setError(null)
    try {
      const connection = await addKnownArtist(artistId, result.id)
      setConnections((current) => [
        connection,
        ...current.filter((item) => item.connectedArtistId !== connection.connectedArtistId),
      ])
      setSearchValue('')
      setSearchResults([])
      setRawSearchResultCount(0)
      onConnectionsChange()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Failed to add artist.')
    } finally {
      setPendingArtistId(null)
    }
  }

  const handleRemove = async (connectedArtistId: number) => {
    setPendingArtistId(connectedArtistId)
    setError(null)
    try {
      await removeKnownArtist(artistId, connectedArtistId)
      setConnections((current) => current.filter((item) => item.connectedArtistId !== connectedArtistId))
      onConnectionsChange()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Failed to remove artist.')
    } finally {
      setPendingArtistId(null)
    }
  }

  const handleSearchSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const firstResult = searchResults[0]
    if (firstResult) void handleAdd(firstResult)
  }

  return (
    <section className="manual-artist-connections" aria-labelledby="manual-artist-connections-heading">
      <div className="biography-section-heading">
        <div>
          <h3 id="manual-artist-connections-heading">Artists you know</h3>
          <p>Manual links used for promoter recommendations.</p>
        </div>
        <span>{connections.length}</span>
      </div>

      <SearchInputField
        inputId="known-artist-search"
        label="Add artist"
        placeholder="Search artists..."
        value={searchValue}
        onChange={setSearchValue}
        onSubmit={handleSearchSubmit}
        onClear={() => {
          setSearchValue('')
          setSearchResults([])
          setRawSearchResultCount(0)
        }}
        showClear={Boolean(searchValue)}
        results={searchResults}
        isLoading={isSearching}
        showResultTabs={false}
        showResultsWhenEmpty
        canLoadMore={canLoadMoreSearchResults}
        onLoadMore={() => setSearchLimit((current) => (
          Math.min(current + SEARCH_RESULT_LIMIT, SEARCH_RESULT_MAX_LIMIT)
        ))}
        onSelectResult={(result) => void handleAdd(result)}
      />

      {error && <p className="biography-message error">{error}</p>}
      {isLoading ? (
        <p>Loading known artists...</p>
      ) : connections.length > 0 ? (
        <div className="manual-artist-connection-list">
          {connections.map((connection) => (
            <div className="manual-artist-connection" key={connection.connectedArtistId}>
              <Link to={`/graph?selectedType=artist&selectedId=${connection.connectedArtistId}`}>
                {connection.connectedArtistName}
              </Link>
              <button
                type="button"
                onClick={() => void handleRemove(connection.connectedArtistId)}
                disabled={pendingArtistId === connection.connectedArtistId}
              >
                {pendingArtistId === connection.connectedArtistId ? 'Removing...' : 'Remove'}
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="biography-empty">No manually linked artists yet.</p>
      )}
    </section>
  )
}
