import ForceGraph2D from 'react-force-graph-2d'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchEgoGraph, fetchGraph, type GraphParams } from '../../api/graph.ts'
import { fetchGenres } from '../../api/genres.ts'
import { useApi } from '../../hooks/useApi.ts'
import { useGraphStore } from '../../store/graphStore.ts'
import { getCssVar, hexToRgba } from '../../styles/colors.ts'
import { graphEntityId, type GraphData, type GraphNode, type NodeType } from '../../types/graph.ts'
import type { SearchEntityType } from '../../types/search.ts'
import { drawNodeShape } from '../hooks/drawNode.ts'
import { useGraphHighlights } from '../hooks/useGraphHighlights.ts'
import { useGraphPhysics } from '../hooks/useGraphPhysics.ts'
import { GraphFilters } from './GraphDataFilter.tsx'
import { GRAPH_NODE_TYPES, GraphNodeFilter } from './GraphNodeFilter.tsx'

const MIN_GRAPH_HEIGHT = 320
const DEFAULT_GRAPH_FILTERS: GraphParams = { limit: 100 }
const EMPTY_GRAPH_DATA: GraphData = { nodes: [], links: [] }
const DEFAULT_VISIBLE_NODE_TYPES = new Set<NodeType>(GRAPH_NODE_TYPES)
type LinkEndpoint = string | { id: string }

function isSearchEntityType(value: string | null): value is SearchEntityType {
  return value === 'artist' || value === 'venue' || value === 'promoter' || value === 'event'
}

function getLinkNodeId(endpoint: LinkEndpoint) {
  return typeof endpoint === 'object' && endpoint !== null ? endpoint.id : endpoint
}

interface ScenegraphMapPanelProps {
  title?: string
  providedData?: GraphData
  showFilters?: boolean
  highlightLinks?: boolean
  highlightPathToNodeId?: string
}

export function ScenegraphMapPanel({
  title,
  providedData,
  showFilters = true,
  highlightLinks = true,
  highlightPathToNodeId,
}: ScenegraphMapPanelProps) {
  const graphRef = useRef<any>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [graphSize, setGraphSize] = useState({ width: 0, height: 0 })
  const [graphFilters, setGraphFilters] = useState<GraphParams>(DEFAULT_GRAPH_FILTERS)
  const [visibleNodeTypes, setVisibleNodeTypes] = useState<Set<NodeType>>(() => new Set(DEFAULT_VISIBLE_NODE_TYPES))
  const [searchParams, setSearchParams] = useSearchParams()
  const { setSelected, selectedNode } = useGraphStore()
  const selectedTypeParam = searchParams.get('selectedType')
  const selectedType = isSearchEntityType(selectedTypeParam) ? selectedTypeParam : null
  const selectedId = searchParams.get('selectedId') ?? ''
  const selectedEntityId = selectedType && selectedId ? graphEntityId(selectedId, selectedType) : null

  const { data, isLoading, error, refetch } = useApi<GraphData>(
    () => {
      if (providedData) {
        return Promise.resolve(providedData)
      }

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
    [providedData, selectedType, selectedId, graphFilters.genre, graphFilters.dateFrom, graphFilters.dateTo, graphFilters.limit]
  )

  const { data: genres, isLoading: isGenresLoading, error: genresError } = useApi(
    () => (showFilters ? fetchGenres() : Promise.resolve([])),
    [showFilters]
  )

  const rawGraphData = data || EMPTY_GRAPH_DATA
  const graphData = useMemo<GraphData>(() => {
    const visibleNodes = rawGraphData.nodes.filter((node) => visibleNodeTypes.has(node.type))
    const visibleNodeIds = new Set(visibleNodes.map((node) => node.id))
    const visibleLinks = rawGraphData.links.filter((link) => (
      visibleNodeIds.has(getLinkNodeId(link.source as LinkEndpoint)) && visibleNodeIds.has(getLinkNodeId(link.target as LinkEndpoint))
    ))

    return {
      centerNodeId: rawGraphData.centerNodeId,
      nodes: visibleNodes,
      links: visibleLinks,
    }
  }, [rawGraphData, visibleNodeTypes])

  const { connectedNodes, pathLinks } = useGraphHighlights(selectedNode || null, graphData, highlightPathToNodeId)
  useGraphPhysics(graphRef, graphData)

  useEffect(() => {
    if (!selectedType || selectedEntityId === null || !data) return

    const nextSelectedNode = data.nodes.find((node) => (
      node.type === selectedType && node.entityId === selectedEntityId
    ))
    if (nextSelectedNode && selectedNode?.id !== nextSelectedNode.id) {
      setSelected(nextSelectedNode)
    }
  }, [data, selectedEntityId, selectedNode?.id, selectedType, setSelected])

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
      nextParams.delete('q')
      nextParams.delete('artist')

      const isSameSelectedNode = selectedNode?.id === nextNode.id
      const isCurrentEgoGraph = selectedType === nextNode.type && selectedEntityId === nextNode.entityId

      if (isSameSelectedNode && !isCurrentEgoGraph) {
        nextParams.set('selectedType', nextNode.type)
        nextParams.set('selectedId', String(nextNode.entityId))
      } else {
        nextParams.delete('selectedType')
        nextParams.delete('selectedId')
      }

      setSearchParams(nextParams, { replace: false })
      setSelected(nextNode)
    },
    [searchParams, selectedEntityId, selectedNode?.id, selectedType, setSearchParams, setSelected]
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

  const handleLegendToggle = useCallback((type: NodeType) => {
    setVisibleNodeTypes((currentTypes) => {
      const nextTypes = new Set(currentTypes)
      if (nextTypes.has(type)) {
        nextTypes.delete(type)
      } else {
        nextTypes.add(type)
      }
      return nextTypes
    })
  }, [])

  const graphBackground = getCssVar('--background')
  const linkHighlight = getCssVar('--link-highlight')
  const linkDim = getCssVar('--link-dim')
  const nodeCount = graphData.nodes.length
  const linkCount = graphData.links.length
  const displayedEventDates = graphData.nodes
    .filter((node) => node.type === 'event')
    .map((node) => node.startDate ?? node.date ?? node.endDate)
    .filter((date): date is string => Boolean(date))
    .sort()
  const displayedDateRange =
    displayedEventDates.length > 0
      ? {
          from: displayedEventDates[0],
          to: displayedEventDates[displayedEventDates.length - 1],
        }
      : null
  const isHighlightedLink = (source: string, target: string) => (
    highlightPathToNodeId
      ? pathLinks.has([source, target].sort().join('|'))
      : connectedNodes.has(source) && connectedNodes.has(target)
  )

  return (
    <section
      className={`scenegraph-map-panel${title ? ' has-heading' : ''}${showFilters ? '' : ' without-filters'}`}
      aria-label="Scenegraph database"
    >
      {title && (
        <div className="scenegraph-map-heading">
          <span className="search-query-label">{title}</span>
        </div>
      )}
      {showFilters && (
        <article className="graph-filter-card scenegraph-map-filters">
          <GraphFilters
            filters={graphFilters}
            genres={genres ?? []}
            isGenresLoading={isGenresLoading}
            genresError={genresError}
            displayedDateRange={displayedDateRange}
            onChange={handleGraphFiltersChange}
          />
        </article>
      )}

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
        <GraphNodeFilter visibleNodeTypes={visibleNodeTypes} onToggle={handleLegendToggle} />
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
            if (highlightLinks && isHighlightedLink(source, target)) {
              return Math.sqrt(l.value ?? l.weight ?? 1) * 2
            }
            return Math.sqrt(l.value ?? l.weight ?? 1)
          }}
          linkColor={(l: any) => {
            const source = typeof l.source === 'object' ? l.source.id : l.source
            const target = typeof l.target === 'object' ? l.target.id : l.target
            if (highlightLinks && isHighlightedLink(source, target)) {
              return hexToRgba(linkHighlight, 0.8)
            }
            return hexToRgba(linkDim, 0.6)
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
          backgroundColor={graphBackground}
          warmupTicks={120}
          cooldownTicks={180}
        />
      </div>
    </section>
  )
}
