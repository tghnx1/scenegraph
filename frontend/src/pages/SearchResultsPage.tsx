import { useEffect, useState, useRef, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import ForceGraph2D from 'react-force-graph-2d'
import { useApi } from '../hooks/useApi'
import { fetchSearch } from '../api/search'
import { fetchGraph } from '../api/graph'
import type { SearchResponse, SearchResult } from '../types/search'
import type { GraphNode } from '../types/graph'
import { drawNodeShape } from './GraphPage/drawNode'
import { LINK_DIM, BACKGROUND, hexToRgba } from '../styles/colors'

const MIN_GRAPH_HEIGHT = 520

function SearchResultCard({ result }: { result: SearchResult }) {
  if (result.type === 'artist') {
    return (
      <article className="search-result-card">
        <div className="result-header">
          <div>
            <span className="result-type">Artist</span>
            <h2>{result.label}</h2>
            <p className="result-meta">{result.genres.join(' · ') || 'No genres yet'}</p>
          </div>
          <span className="result-badge">{result.eventCount} events</span>
        </div>

        {result.bio && <p className="result-description">{result.bio}</p>}

        <section className="result-section">
          <h3>Events participated</h3>
          <div className="result-list">
            {result.events.map((event) => (
              <div key={event.id} className="result-tile">
                <strong>{event.label}</strong>
                <span>{event.date}</span>
                <span>{event.venueName}</span>
                <span>{event.artists.join(' · ')}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="result-section">
          <h3>Connected artists</h3>
          <div className="result-pills">
            {result.connectedArtists.map((artist) => (
              <Link key={artist.id} to={`/artist/${artist.id}`} className="result-pill">
                {artist.label} <span>{artist.sharedEvents} shared</span>
              </Link>
            ))}
          </div>
        </section>
      </article>
    )
  }

  if (result.type === 'venue') {
    return (
      <article className="search-result-card">
        <div className="result-header">
          <div>
            <span className="result-type">Venue</span>
            <h2>{result.label}</h2>
            <p className="result-meta">
              {result.address ?? 'Address not provided'}
              {result.district ? ` · ${result.district}` : ''}
            </p>
          </div>
          <span className="result-badge">{result.eventCount} events</span>
        </div>

        <section className="result-section">
          <h3>Events conducted here</h3>
          <div className="result-list">
            {result.events.map((event) => (
              <div key={event.id} className="result-tile">
                <strong>{event.label}</strong>
                <span>{event.date}</span>
                <span>{event.artists.join(' · ')}</span>
                <span>{event.promoters.join(' · ')}</span>
              </div>
            ))}
          </div>
        </section>
      </article>
    )
  }

  if (result.type === 'promoter') {
    return (
      <article className="search-result-card">
        <div className="result-header">
          <div>
            <span className="result-type">Promoter</span>
            <h2>{result.label}</h2>
          </div>
          <span className="result-badge">{result.eventCount} events</span>
        </div>

        <section className="result-section">
          <h3>Events organized</h3>
          <div className="result-list">
            {result.events.map((event) => (
              <div key={event.id} className="result-tile">
                <strong>{event.label}</strong>
                <span>{event.date}</span>
                <span>{event.venueName}</span>
                <span>{event.artists.join(' · ')}</span>
              </div>
            ))}
          </div>
        </section>
      </article>
    )
  }

  return (
    <article className="search-result-card">
      <div className="result-header">
        <div>
          <span className="result-type">Event</span>
          <h2>{result.label}</h2>
          <p className="result-meta">{result.date}</p>
        </div>
        <span className="result-badge">Live event</span>
      </div>

      <section className="result-section">
        <h3>Venue</h3>
        <p className="result-description">{result.venue.label}</p>
      </section>

      <section className="result-section two-column">
        <div>
          <h3>Artists</h3>
          <div className="result-pills compact">
            {result.artists.map((artist) => (
              <Link key={artist.id} to={`/artist/${artist.id}`} className="result-pill">
                {artist.label}
              </Link>
            ))}
          </div>
        </div>
        <div>
          <h3>Promoters</h3>
          <div className="result-pills compact">
            {result.promoters.map((promoter) => (
              <span key={promoter.id} className="result-pill muted">
                {promoter.label}
              </span>
            ))}
          </div>
        </div>
      </section>
    </article>
  )
}

export function SearchResultsPage() {
  const [searchParams] = useSearchParams()
  const query = searchParams.get('q') ?? ''
  const graphRef = useRef<any>(null)
  const graphContainerRef = useRef<HTMLDivElement | null>(null)
  const [graphSize, setGraphSize] = useState({ width: 0, height: 0 })
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)

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

  const { data: graphData, isLoading: isGraphLoading } = useApi(
    () => fetchGraph({ genre: undefined }),
    []
  )

  const results = searchData?.results ?? []

  // Filter graph to show only searched entity and connected neighbors (2 levels deep)
const filteredGraphData = useCallback(() => {
  if (!graphData || !results) return graphData

  // find the primary searched node id from 'results' (pick the first match)
  const searchedNode = results[0]?.id
  if (!searchedNode) return graphData

  // BFS to collect the full connected component (same algorithm as useGraphHighlights)
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

  // filter nodes and links to the visited set
  const nodes = (graphData.nodes || []).filter((n: any) => visited.has(n.id))
  const links = (graphData.links || []).filter((l: any) => {
    const s = typeof l.source === 'object' ? l.source.id : l.source
    const t = typeof l.target === 'object' ? l.target.id : l.target
    return visited.has(s) && visited.has(t)
  })

  return { nodes, links }
}, [graphData, results])

  const handleNodeClick = useCallback((node: object) => {
    const n = node as GraphNode
    setSelectedNode(n)
  }, [])

  return (
    <div className="search-page-shell">
      <div className="search-results-two-column">
        <section className="search-results-shell">
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
              <SearchResultCard key={`${result.type}-${result.id}`} result={result} />
            ))}
          </div>
        </section>

        <div ref={graphContainerRef} className="search-graph-column">
          {isGraphLoading ? (
            <p style={{ padding: 24, color: 'var(--nord-text-muted)' }}>Loading graph...</p>
          ) : (
            <ForceGraph2D
              ref={graphRef}
              width={graphSize.width || undefined}
              height={graphSize.height || undefined}
              graphData={filteredGraphData() || { nodes: [], links: [] }}
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
          )}
        </div>
      </div>
    </div>
  )
}
