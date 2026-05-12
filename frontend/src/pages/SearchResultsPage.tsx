import { useEffect, useState, useRef, useCallback, type FormEvent, useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import ForceGraph2D from 'react-force-graph-2d'
import { useApi } from '../hooks/useApi'
import { fetchSearch } from '../api/search'
import { fetchGraph } from '../api/graph'
import type { SearchResponse } from '../types/search'
import type { GraphNode } from '../types/graph'
import { drawNodeShape } from './GraphPage/drawNode'
import { LINK_DIM, BACKGROUND, hexToRgba } from '../styles/colors'
import { SearchResultCard } from '../components/SearchResultCard'

const MIN_GRAPH_HEIGHT = 520

export function SearchResultsPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const query = searchParams.get('q') ?? ''
  const [searchValue, setSearchValue] = useState(query)
  const graphRef = useRef<any>(null)
  const graphContainerRef = useRef<HTMLDivElement | null>(null)
  const [graphSize, setGraphSize] = useState({ width: 0, height: 0 })
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)

  useEffect(() => {
    setSearchValue(query)
  }, [query])

  useEffect(() => {    const container = graphContainerRef.current
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

  const { data: searchData, isLoading: isSearchLoading, error: searchError } = useApi<SearchResponse>(
    () => fetchSearch(query),
    [query]
  )

  const { data: graphData } = useApi(
    () => fetchGraph({ genre: undefined }),
    []
  )

  const results = searchData?.results ?? []

  // Memoize filtered graph to avoid recalculating on every render
  const filteredGraphData = useMemo(() => {
    if (!graphData || !results) return graphData

    const searchedNode = results[0]?.id
    if (!searchedNode) return graphData

    const visited = new Set<string>([searchedNode])
    const queue: string[] = [searchedNode]

    while (queue.length > 0) {
      const current = queue.shift()!
      graphData.links?.forEach((link: any) => {
        const source = typeof link.source === 'object' ? link.source.id : link.source
        const target = typeof link.target === 'object' ? link.target.id : link.target

        if (source === current && !visited.has(target)) {
          visited.add(target)
          queue.push(target)
        }
        if (target === current && !visited.has(source)) {
          visited.add(source)
          queue.push(source)
        }
      })
    }

    const nodes = (graphData.nodes || []).filter((n: any) => visited.has(n.id))
    const links = (graphData.links || []).filter((l: any) => {
      const s = typeof l.source === 'object' ? l.source.id : l.source
      const t = typeof l.target === 'object' ? l.target.id : l.target
      return visited.has(s) && visited.has(t)
    })

    return { nodes, links }
  }, [graphData, results])

  const handleSearchSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      const nextQuery = searchValue.trim()
      if (!nextQuery) return
      navigate(`/search?q=${encodeURIComponent(nextQuery)}`)
    },
    [navigate, searchValue]
  )

  const handleClearSearch = useCallback(() => {
    setSearchValue('')
    navigate('/search')
  }, [navigate])

  const handleNodeClick = useCallback((node: object) => {
    const n = node as GraphNode
    setSelectedNode(n)
  }, [])

  return (
    <div className="search-page-shell">
      <div className="search-results-two-column">
        <section className="search-results-shell">
          <div className="search-query-panel">
            <form className="search-query-form" onSubmit={handleSearchSubmit}>
              <label className="search-query-label" htmlFor="search-query-input">
                Search catalog
              </label>
              <div className="search-query-box">
                <input
                  id="search-query-input"
                  className="search-query-input"
                  type="search"
                  value={searchValue}
                  onChange={(event) => setSearchValue(event.target.value)}
                  placeholder="Search artists, venues, promoters, events..."
                  aria-label="Search"
                />
                {searchValue && (
                  <button type="button" className="search-query-clear" onClick={handleClearSearch}>
                    Clear
                  </button>
                )}
              </div>
            </form>
            <p className="search-query-hint">Enter a name, then press Enter to update the search.</p>
          </div>

          <div className="search-summary">
            <div>
              <p className="result-type">Query</p>
              <h2>{query || 'Start typing a name'}</h2>
            </div>
            <span className="result-badge">{results.length} matches</span>
          </div>

          {isSearchLoading && <p className="empty-state">Loading search results...</p>}
          {searchError && <p className="error">{searchError}</p>}
          {!isSearchLoading && !searchError && query && results.length === 0 && (
            <div className="empty-state">
              <h3>No matches found</h3>
              <p>Try a shorter query or search by artist, venue, promoter, or event name.</p>
            </div>
          )}

          <div className="search-results-list">
            {results.map((result) => (
              <div key={`${result.type}-${result.id}`}>
                <SearchResultCard result={result} />
              </div>
            ))}
          </div>
        </section>

        <div ref={graphContainerRef} className="search-graph-column">
          <ForceGraph2D
            ref={graphRef}
            width={graphSize.width || undefined}
            height={graphSize.height || undefined}
            graphData={filteredGraphData || { nodes: [], links: [] }}
            nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D) => {
              drawNodeShape(ctx, node.x, node.y, 5, node.type, selectedNode?.id === node.id)
            }}
            nodeColor={() => 'transparent'}
            nodeRelSize={3}
            nodeVal={(n: any) => (selectedNode?.id === n.id ? 3 : 1)}
            nodeLabel={(n: any) => n.label ?? n.id}
            linkWidth={() => 1}
            linkColor={() => hexToRgba(LINK_DIM, 0.6)}
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
    </div>
  )
}
