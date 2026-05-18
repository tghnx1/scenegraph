import ForceGraph2D from 'react-force-graph-2d'
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useApi } from '../hooks/useApi.ts'
import { fetchArtist, fetchSimilarArtists } from '../api/artists.ts'
import { fetchEgoGraph, fetchGraph, type GraphParams } from '../api/graph.ts'
import { fetchGenres } from '../api/genres.ts'
import { fetchSearch, fetchSearchResultById } from '../api/search.ts'
import { useGraphStore } from '../store/graphStore.ts'
import type { Artist, SimilarArtist } from '../types/artist.ts'
import type { GraphNode } from '../types/graph.ts'
import type { SearchEntityType, SearchResponse, SearchResult } from '../types/search.ts'
import { useDebouncedValue } from './hooks/useDebouncedValue.ts'
import { useGraphHighlights } from './hooks/useGraphHighlights.ts'
import { useGraphPhysics } from './hooks/useGraphPhysics.ts'
import { drawNodeShape } from './GraphPage/drawNode.ts'
import { LINK_HIGHLIGHT, LINK_DIM, BACKGROUND, hexToRgba } from '../styles/colors.ts'
import { GraphSidebarDetails } from './components/DetailsPanel.tsx'
import { GraphFilters } from './components/GraphFilters.tsx'
import { SearchQueryForm } from './components/SearchQueryForm.tsx'

const MIN_GRAPH_HEIGHT = 320
const DEFAULT_GRAPH_FILTERS: GraphParams = { limit: 100 }
const NODE_LEGEND_ITEMS = [
  { type: 'artist', label: 'Artist' },
  { type: 'venue', label: 'Venue' },
  { type: 'promoter', label: 'Promoter' },
  { type: 'event', label: 'Event' },
]

function isSearchEntityType(value: string | null): value is SearchEntityType {
  return value === 'artist' || value === 'venue' || value === 'promoter' || value === 'event'
}

export function GraphPage() {
  const graphRef = useRef<any>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [graphSize, setGraphSize] = useState({ width: 0, height: 0 })
  const [graphFilters, setGraphFilters] = useState<GraphParams>(DEFAULT_GRAPH_FILTERS)
  const [searchParams, setSearchParams] = useSearchParams()
  const { setSelected, selectedNode } = useGraphStore()
  const submittedQuery = searchParams.get('q') ?? ''
  const selectedTypeParam = searchParams.get('selectedType')
  const selectedType = isSearchEntityType(selectedTypeParam) ? selectedTypeParam : null
  const selectedId = searchParams.get('selectedId') ?? ''
  const [searchValue, setSearchValue] = useState(submittedQuery)
  const [selectedSearchResult, setSelectedSearchResult] = useState<SearchResult | null>(null)
  const debouncedSearchValue = useDebouncedValue(searchValue.trim(), 350)
  const selectedArtistId = selectedNode?.type === 'artist' ? selectedNode.id : null

  const { data, isLoading, error, refetch } = useApi(
    () => {
      if (selectedType && selectedId) {
        return fetchEgoGraph({
          type: selectedType,
          id: selectedId,
          depth: 1,
          limit: graphFilters.limit ?? DEFAULT_GRAPH_FILTERS.limit,
        })
      }

      return fetchGraph(graphFilters)
    },
    [selectedType, selectedId, graphFilters.genre, graphFilters.dateFrom, graphFilters.dateTo, graphFilters.limit]
  )

  const { data: selectedArtist } = useApi<Artist | null>(
    () => (selectedArtistId ? fetchArtist(selectedArtistId) : Promise.resolve(null)),
    [selectedArtistId]
  )

  const { data: similarArtists } = useApi<SimilarArtist[]>(
    () => (selectedArtistId ? fetchSimilarArtists(selectedArtistId) : Promise.resolve([] as SimilarArtist[])),
    [selectedArtistId]
  )

  const { data: genres, isLoading: isGenresLoading, error: genresError } = useApi(
    () => fetchGenres(),
    []
  )

  const {
    data: searchData,
    isLoading: isSearchLoading,
    error: searchError,
  } = useApi<SearchResponse>(
    () => (submittedQuery ? fetchSearch(submittedQuery) : Promise.resolve({ query: '', results: [] })),
    [submittedQuery]
  )

  const { data: dropdownSearchData, isLoading: isDropdownSearchLoading } = useApi<SearchResponse>(
    () => (debouncedSearchValue.length >= 2 ? fetchSearch(debouncedSearchValue) : Promise.resolve({ query: '', results: [] })),
    [debouncedSearchValue]
  )

  const {
    data: selectedResultFromUrl,
    isLoading: isSelectedResultLoading,
    error: selectedResultError,
  } = useApi<SearchResult | null>(
    () => (
      selectedType && selectedId
        ? fetchSearchResultById(selectedType, selectedId, submittedQuery)
        : Promise.resolve(null)
    ),
    [selectedType, selectedId, submittedQuery]
  )

  const { connectedNodes } = useGraphHighlights(selectedNode || null, data)
  useGraphPhysics(graphRef, data)

  useEffect(() => {
    setSearchValue(submittedQuery)
  }, [submittedQuery])

  useEffect(() => {
    if (!selectedType || !selectedId) {
      setSelectedSearchResult(null)
    }
  }, [selectedType, selectedId])

  useEffect(() => {
    if (!selectedType || !selectedId || !data) return

    const nextSelectedNode = data.nodes.find((node) => node.id === selectedId)
    if (nextSelectedNode && selectedNode?.id !== nextSelectedNode.id) {
      setSelected(nextSelectedNode)
    }
  }, [data, selectedId, selectedNode?.id, selectedType, setSelected])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const updateSize = () => {
      const rect = container.getBoundingClientRect()
      setGraphSize({
        width: Math.floor(rect.width),
        height: Math.max(Math.floor(rect.height), MIN_GRAPH_HEIGHT),
      })
    }

    updateSize()

    const resizeObserver = new ResizeObserver(updateSize)
    resizeObserver.observe(container)

    return () => resizeObserver.disconnect()
  }, [])

  const handleNodeClick = useCallback(
    (node: object) => {
      const nextNode = node as GraphNode
      const nextParams = new URLSearchParams(searchParams)
      nextParams.set('q', nextNode.name)
      nextParams.delete('artist')

      const isSameSelectedNode = selectedNode?.id === nextNode.id
      const isCurrentEgoGraph = selectedType === nextNode.type && selectedId === nextNode.id

      if (isSameSelectedNode && !isCurrentEgoGraph) {
        nextParams.set('selectedType', nextNode.type)
        nextParams.set('selectedId', nextNode.id)
      } else {
        nextParams.delete('selectedType')
        nextParams.delete('selectedId')
      }

      setSearchParams(nextParams, { replace: false })
      setSelectedSearchResult(null)
      setSelected(nextNode)
    },
    [searchParams, selectedId, selectedNode?.id, selectedType, setSearchParams, setSelected]
  )

  const handleSearchSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      const nextQuery = searchValue.trim()
      if (!nextQuery) return
      const nextParams = new URLSearchParams(searchParams)
      nextParams.set('q', nextQuery)
      nextParams.delete('artist')
      nextParams.delete('selectedType')
      nextParams.delete('selectedId')
      setSelectedSearchResult(null)
      setSelected(null)
      setSearchParams(nextParams, { replace: true })
    },
    [searchParams, searchValue, setSearchParams, setSelected]
  )

  const handleClearSearch = useCallback(() => {
    setSearchValue('')
    const nextParams = new URLSearchParams(searchParams)
    nextParams.delete('q')
    nextParams.delete('artist')
    nextParams.delete('selectedType')
    nextParams.delete('selectedId')
    setSearchParams(nextParams, { replace: true })
    setSelectedSearchResult(null)
    setSelected(null)
  }, [searchParams, setSearchParams, setSelected])

  const handleSearchValueChange = useCallback((nextValue: string) => {
    setSearchValue(nextValue)
  }, [])

  const handleSelectSearchResult = useCallback(
    (result: SearchResult) => {
      const nextParams = new URLSearchParams(searchParams)
      nextParams.set('q', result.label)
      nextParams.set('selectedType', result.type)
      nextParams.set('selectedId', result.id)
      nextParams.delete('artist')
      setSearchValue(result.label)
      setSelectedSearchResult(result)
      setSelected(null)
      setSearchParams(nextParams, { replace: false })
    },
    [searchParams, setSearchParams, setSelected]
  )

  const handleGraphFiltersChange = useCallback(
    (nextFilters: GraphParams) => {
      setGraphFilters(nextFilters)
      setSelected(null)

      if (searchParams.has('artist')) {
        const nextParams = new URLSearchParams(searchParams)
        nextParams.delete('artist')
        setSearchParams(nextParams, { replace: true })
      }
    },
    [searchParams, setSearchParams, setSelected]
  )

  const similarArtistLinks = similarArtists ?? []
  const searchResults = searchData?.results ?? []
  const activeSelectedSearchResult =
    selectedSearchResult?.type === selectedType && selectedSearchResult.id === selectedId
      ? selectedSearchResult
      : selectedResultFromUrl
  const trimmedSearchValue = searchValue.trim()
  const isDropdownWaiting = trimmedSearchValue.length >= 2 && debouncedSearchValue !== trimmedSearchValue
  const dropdownSearchResults = debouncedSearchValue === trimmedSearchValue ? dropdownSearchData?.results ?? [] : []
  const detailSearchResults = activeSelectedSearchResult ? [activeSelectedSearchResult] : searchResults
  const detailsSearchError = selectedResultError ?? searchError
  const isDetailsSearchLoading = isSelectedResultLoading || isSearchLoading
  const hasActiveSearchState = Boolean(searchValue || submittedQuery || selectedNode)
  const graphData = data || { nodes: [], links: [] }
  const nodeCount = graphData.nodes.length
  const linkCount = graphData.links.length

  return (
    <div className="graph-page-shell">
      <aside className="graph-sidebar">
        <article className="graph-sidebar-card">
          <div className="graph-sidebar-search">
            <SearchQueryForm
              inputId="graph-search-query-input"
              value={searchValue}
              onChange={handleSearchValueChange}
              onSubmit={handleSearchSubmit}
              onClear={handleClearSearch}
              showClear={hasActiveSearchState}
              results={dropdownSearchResults}
              isLoading={isDropdownWaiting || isDropdownSearchLoading}
              onSelectResult={handleSelectSearchResult}
            />
            {/* <p className="search-query-hint">Enter a name, then press Enter to update the search.</p> */}
          </div>

          <GraphFilters
            filters={graphFilters}
            genres={genres ?? []}
            isGenresLoading={isGenresLoading}
            genresError={genresError}
            onChange={handleGraphFiltersChange}
          />

          <GraphSidebarDetails
            searchQuery={submittedQuery}
            searchResults={detailSearchResults}
            isSearchLoading={isDetailsSearchLoading}
            searchError={detailsSearchError}
            selectedNode={activeSelectedSearchResult ? null : selectedNode}
            selectedArtist={selectedArtist}
            similarArtists={similarArtistLinks}
          />
        </article>
      </aside>

      <div ref={containerRef} className="graph-canvas graph-canvas--large">
        {isLoading && !data && <div className="graph-canvas-status">Loading graph...</div>}
        {error && (
          <div className="graph-canvas-status error">
            {error} <button onClick={refetch}>retry</button>
          </div>
        )}
        <div className="graph-canvas-counts" aria-label={`${nodeCount} nodes and ${linkCount} links displayed`}>
          <span>{nodeCount} nodes</span>
          <span>{linkCount} links</span>
        </div>
        <div className="graph-legend" aria-label="Graph entity legend">
          {NODE_LEGEND_ITEMS.map((item) => (
            <div className="graph-legend-item" key={item.type}>
              <span className={`graph-legend-marker graph-legend-marker--${item.type}`} aria-hidden="true" />
              <span>{item.label}</span>
            </div>
          ))}
        </div>
        <ForceGraph2D
          ref={graphRef}
          width={graphSize.width || undefined}
          height={graphSize.height || undefined}
          graphData={graphData}
          nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D) => {
            drawNodeShape(ctx, node.x, node.y, 5, node.type, selectedNode?.id === node.id)
          }}
          nodeColor={() => 'transparent'}
          nodeRelSize={3}
          nodeVal={(n: any) => (selectedNode?.id === n.id ? 3 : 1)}
          nodeLabel={(n: any) => n.name ?? n.label ?? n.id}
          linkWidth={(l: any) => {
            const source = typeof l.source === 'object' ? l.source.id : l.source
            const target = typeof l.target === 'object' ? l.target.id : l.target
            if (connectedNodes.has(source) && connectedNodes.has(target)) {
              return Math.sqrt(l.value ?? l.weight ?? 1) * 2
            }
            return Math.sqrt(l.value ?? l.weight ?? 1)
          }}
          linkColor={(l: any) => {
            const source = typeof l.source === 'object' ? l.source.id : l.source
            const target = typeof l.target === 'object' ? l.target.id : l.target
            if (connectedNodes.has(source) && connectedNodes.has(target)) {
              return hexToRgba(LINK_HIGHLIGHT, 0.8)
            }
            return hexToRgba(LINK_DIM, 0.6)
          }}
          enableNodeDrag
          onNodeDrag={(node: any) => {
            node.fx = node.x
            node.fy = node.y
          }}
          onNodeDragEnd={(node: any) => {
            node.fx = null
            node.fy = null
          }}
          onNodeClick={handleNodeClick}
          backgroundColor={BACKGROUND}
          warmupTicks={120}
          cooldownTicks={180}
        />
      </div>
    </div>
  )
}
