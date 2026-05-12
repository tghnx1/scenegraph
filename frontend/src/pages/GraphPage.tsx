import ForceGraph2D from 'react-force-graph-2d'
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useApi } from '../hooks/useApi.ts'
import { fetchArtist, fetchSimilarArtists } from '../api/artists.ts'
import { fetchGraph, type GraphParams } from '../api/graph.ts'
import { fetchSearch } from '../api/search.ts'
import { useGraphStore } from '../store/graphStore.ts'
import type { Artist, SimilarArtist } from '../types/artist.ts'
import type { GraphNode } from '../types/graph.ts'
import type { SearchResponse } from '../types/search.ts'
import { useGraphHighlights } from './GraphPage/hooks/useGraphHighlights.ts'
import { useGraphPhysics } from './GraphPage/hooks/useGraphPhysics.ts'
import { drawNodeShape } from './GraphPage/drawNode.ts'
import { LINK_HIGHLIGHT, LINK_DIM, BACKGROUND, hexToRgba } from '../styles/colors.ts'
import { GraphSidebarDetails } from './GraphPage/components/DetailsPanel.tsx'
import { GraphFilters } from './GraphPage/components/GraphFilters.tsx'

const MIN_GRAPH_HEIGHT = 320
const DEFAULT_GRAPH_FILTERS: GraphParams = { limit: 500 }

export function GraphPage() {
  const graphRef = useRef<any>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [graphSize, setGraphSize] = useState({ width: 0, height: 0 })
  const [searchValue, setSearchValue] = useState('')
  const [graphFilters, setGraphFilters] = useState<GraphParams>(DEFAULT_GRAPH_FILTERS)
  const [searchParams, setSearchParams] = useSearchParams()
  const { setSelected, selectedNode } = useGraphStore()
  const submittedQuery = searchParams.get('q') ?? ''
  const selectedArtistParam = searchParams.get('artist') ?? ''
  const selectedArtistId = selectedNode?.type === 'artist' ? selectedNode.id : null

  const { data, isLoading, error, refetch } = useApi(
    () => fetchGraph(graphFilters),
    [graphFilters.genre, graphFilters.dateFrom, graphFilters.dateTo, graphFilters.limit]
  )

  const { data: selectedArtist, isLoading: isArtistLoading, error: artistError } = useApi<Artist | null>(
    () => (selectedArtistId ? fetchArtist(selectedArtistId) : Promise.resolve(null)),
    [selectedArtistId]
  )

  const { data: similarArtists } = useApi<SimilarArtist[]>(
    () => (selectedArtistId ? fetchSimilarArtists(selectedArtistId) : Promise.resolve([] as SimilarArtist[])),
    [selectedArtistId]
  )

  const {
    data: searchData,
    isLoading: isSearchLoading,
    error: searchError,
  } = useApi<SearchResponse>(
    () => (submittedQuery ? fetchSearch(submittedQuery) : Promise.resolve({ query: '', results: [] })),
    [submittedQuery]
  )

  const { connectedNodes } = useGraphHighlights(selectedNode || null, data)
  useGraphPhysics(graphRef, data)

  useEffect(() => {
    setSearchValue(submittedQuery)
  }, [submittedQuery])

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

  useEffect(() => {
    if (!selectedArtistParam || !data) return

    const matchedNode = data.nodes?.find((node: any) => node.id === selectedArtistParam)
    if (matchedNode && matchedNode.id !== selectedNode?.id) {
      setSelected(matchedNode as GraphNode)
    }
  }, [data, selectedArtistParam, selectedNode?.id, setSelected])

  const handleNodeClick = useCallback(
    (node: object) => {
      const nextNode = node as GraphNode
      const nextParams = new URLSearchParams(searchParams)
      nextParams.delete('q')
      if (nextNode.type === 'artist') {
        nextParams.set('artist', nextNode.id)
      } else {
        nextParams.delete('artist')
      }

      setSearchParams(nextParams, { replace: true })
      setSelected(nextNode)
    },
    [searchParams, setSearchParams, setSelected]
  )

  const handleSearchSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      const nextQuery = searchValue.trim()
      if (!nextQuery) return
      const nextParams = new URLSearchParams(searchParams)
      nextParams.set('q', nextQuery)
      nextParams.delete('artist')
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
    setSearchParams(nextParams, { replace: true })
    setSelected(null)
  }, [searchParams, setSearchParams, setSelected])

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
  const hasActiveSearchState = Boolean(searchValue || submittedQuery || selectedNode)
  const graphData = data || { nodes: [], links: [] }

  return (
    <div className="graph-page-shell">
      <aside className="graph-sidebar">
        <article className="graph-sidebar-card">
          <div className="graph-sidebar-search">
            <form className="search-query-form" onSubmit={handleSearchSubmit}>
              <label className="search-query-label" htmlFor="graph-search-query-input">
                Search Database
              </label>
              <div className="search-query-box">
                <input
                  id="graph-search-query-input"
                  className="search-query-input"
                  type="search"
                  value={searchValue}
                  onChange={(event) => setSearchValue(event.target.value)}
                  placeholder="Search artists, venues, promoters, events..."
                  aria-label="Search"
                />
                {hasActiveSearchState && (
                  <button type="button" className="search-query-clear" onClick={handleClearSearch} aria-label="Clear search and selection">
                    x
                  </button>
                )}
              </div>
            </form>
            {/* <p className="search-query-hint">Enter a name, then press Enter to update the search.</p> */}
          </div>

          <GraphFilters filters={graphFilters} onChange={handleGraphFiltersChange} />

          <GraphSidebarDetails
            searchQuery={submittedQuery}
            searchResults={searchResults}
            isSearchLoading={isSearchLoading}
            searchError={searchError}
            selectedNode={selectedNode}
            selectedArtist={selectedArtist}
            isArtistLoading={isArtistLoading}
            artistError={artistError}
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
          nodeLabel={(n: any) => n.label ?? n.id}
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
