import { useCallback, useState, type FormEvent } from 'react'
import { fetchSearch } from '../api/search'
import { useApi } from '../hooks/useApi'
import type { SearchResponse, SearchResult } from '../types/search'
import { SearchQueryForm } from './components/SearchQuery'
import { useDebouncedValue } from './hooks/useDebouncedValue'
import { ProfilePage } from './ProfilePage'

const EMPTY_SEARCH_RESPONSE: SearchResponse = { query: '', results: [] }

export function AgencyPage() {
  const [artistSearchValue, setArtistSearchValue] = useState('')
  const [selectedArtist, setSelectedArtist] = useState<SearchResult | null>(null)
  const debouncedArtistSearchValue = useDebouncedValue(artistSearchValue.trim(), 350)
  const shouldFetchArtistSearch =
    debouncedArtistSearchValue.length >= 2 &&
    debouncedArtistSearchValue === artistSearchValue.trim()

  const { data: artistSearchData, isLoading: isArtistSearchLoading } = useApi<SearchResponse>(
    () => (
      shouldFetchArtistSearch
        ? fetchSearch(debouncedArtistSearchValue)
        : Promise.resolve(EMPTY_SEARCH_RESPONSE)
    ),
    [debouncedArtistSearchValue, shouldFetchArtistSearch]
  )

  const artistResults = (artistSearchData?.results ?? []).filter((result) => result.type === 'artist')
  const isArtistSearchWaiting = artistSearchValue.trim().length >= 2 && debouncedArtistSearchValue !== artistSearchValue.trim()

  const handleArtistSearchChange = useCallback((nextValue: string) => {
    setArtistSearchValue(nextValue)
    setSelectedArtist((currentArtist) => (
      currentArtist && currentArtist.name !== nextValue ? null : currentArtist
    ))
  }, [])

  const handleArtistSearchSubmit = useCallback((event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const firstArtistResult = artistResults[0]
    if (!firstArtistResult) return
    setSelectedArtist(firstArtistResult)
    setArtistSearchValue(firstArtistResult.name)
  }, [artistResults])

  const handleSelectArtist = useCallback((result: SearchResult) => {
    if (result.type !== 'artist') return
    setSelectedArtist(result)
    setArtistSearchValue(result.name)
  }, [])

  const handleClearArtistSearch = useCallback(() => {
    setArtistSearchValue('')
    setSelectedArtist(null)
  }, [])

  return (
    <ProfilePage
      recommendationTargetControls={{
        artistId: selectedArtist?.id ?? null,
        emptyMessage: selectedArtist
          ? `Click "Get Rec" to load promoter recommendations for ${selectedArtist.name}.`
          : 'Search and select an artist, then click "Get Rec" to load promoter recommendations.',
        getButtonLabel: 'Get Rec',
        controls: (
          <div className="agency-artist-recommendation-search">
            <SearchQueryForm
              inputId="agency-recommendation-artist-search"
              label=""
              placeholder="Search artists..."
              value={artistSearchValue}
              onChange={handleArtistSearchChange}
              onSubmit={handleArtistSearchSubmit}
              onClear={handleClearArtistSearch}
              showClear={Boolean(artistSearchValue || selectedArtist)}
              results={artistResults}
              isLoading={isArtistSearchWaiting || isArtistSearchLoading}
              onSelectResult={handleSelectArtist}
            />
          </div>
        ),
      }}
    />
  )
}
