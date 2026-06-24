import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { SEARCH_RESULT_LIMIT, SEARCH_RESULT_MAX_LIMIT, fetchSearch } from '../api/search'
import { useApi } from '../api/useApi'
import type { SearchResponse, SearchResult } from '../types/search'
import { SearchInputField } from './components/SearchInputField'
import { useDebouncedValue } from './hooks/useDebouncedValue'
import { ProfilePage } from './ProfilePage'

const EMPTY_SEARCH_RESPONSE: SearchResponse = { query: '', results: [] }

export function AgencyPage() {
  const [artistSearchValue, setArtistSearchValue] = useState('')
  const [selectedArtist, setSelectedArtist] = useState<SearchResult | null>(null)
  const [artistSearchLimit, setArtistSearchLimit] = useState(SEARCH_RESULT_LIMIT)
  const debouncedArtistSearchValue = useDebouncedValue(artistSearchValue.trim(), 350)
  const shouldFetchArtistSearch =
    debouncedArtistSearchValue.length >= 2 &&
    debouncedArtistSearchValue === artistSearchValue.trim()

  const { data: artistSearchData, isLoading: isArtistSearchLoading } = useApi<SearchResponse>(
    () => (
      shouldFetchArtistSearch
        ? fetchSearch(debouncedArtistSearchValue, artistSearchLimit, 'artist')
        : Promise.resolve(EMPTY_SEARCH_RESPONSE)
    ),
    [artistSearchLimit, debouncedArtistSearchValue, shouldFetchArtistSearch]
  )

  const artistResults = (artistSearchData?.results ?? []).filter((result) => result.type === 'artist')
  const isArtistSearchWaiting = artistSearchValue.trim().length >= 2 && debouncedArtistSearchValue !== artistSearchValue.trim()
  const canLoadMoreArtistResults =
    shouldFetchArtistSearch &&
    !isArtistSearchWaiting &&
    !isArtistSearchLoading &&
    artistSearchLimit < SEARCH_RESULT_MAX_LIMIT &&
    artistResults.length >= artistSearchLimit

  useEffect(() => {
    setArtistSearchLimit(SEARCH_RESULT_LIMIT)
  }, [debouncedArtistSearchValue])

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

  const handleLoadMoreArtistResults = useCallback(() => {
    setArtistSearchLimit((currentLimit) => Math.min(currentLimit + SEARCH_RESULT_LIMIT, SEARCH_RESULT_MAX_LIMIT))
  }, [])

  return (
    <ProfilePage
      showBiography={false}
      recommendationTargetControls={{
        artistId: selectedArtist?.id ?? null,
        emptyMessage: selectedArtist
          ? `Click "Get Rec" to load promoter recommendations for ${selectedArtist.name}. Loading time may be quite long. Let the wizard does its magic.`
          : 'Search and select an artist, then click "Get Rec" to load promoter recommendations. Loading time may be quite long.',
        getButtonLabel: 'Get Rec',
        controls: (
          <div className="w-[clamp(240px,28vw,360px)] min-w-0 shrink max-[900px]:w-full">
            <SearchInputField
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
              showResultTabs={false}
              canLoadMore={canLoadMoreArtistResults}
              onLoadMore={handleLoadMoreArtistResults}
              onSelectResult={handleSelectArtist}
            />
          </div>
        ),
      }}
    />
  )
}
