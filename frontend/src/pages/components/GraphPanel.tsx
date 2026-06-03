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
const DEFAULT_VISIBLE_NODE_TYPES = new Set<NodeType>(
  GRAPH_NODE_TYPES.filter((nodeType) => nodeType !== 'venue'),
)
type LinkEndpoint = string | { id: string }

// Guard URL param values before using entity-specific fetch logic.
function isSearchEntityType(value: string | null): value is SearchEntityType {
  return value === 'artist' || value === 'venue' || value === 'promoter' || value === 'event'
}

// Normalize ForceGraph link endpoints to plain node ids.
function getLinkNodeId(endpoint: LinkEndpoint) {
  return typeof endpoint === 'object' && endpoint !== null ? endpoint.id : endpoint
}

// Build a stable link key so path lookups work regardless of direction.
function getUndirectedLinkKey(source: string, target: string) {
  return [source, target].sort().join('|')
}

// Extract a normalized strength-like value from link payload for visual scaling.
function getLinkStrengthValue(link: { strength?: unknown; weight?: unknown; value?: unknown }) {
  const candidates = [link.strength, link.weight, link.value]
  for (const candidate of candidates) {
    if (typeof candidate === 'number' && Number.isFinite(candidate)) {
      return Math.max(0, candidate)
    }
  }
  return 0
}

function getLinkDashPattern(link: { style?: unknown }) {
  if (link.style === 'dashed') return [6, 4]
  if (link.style === 'dotted') return [2, 4]
  return null
}

interface ScenegraphMapPanelProps {
  title?: string
  providedData?: GraphData
  showFilters?: boolean
  showNodeTypeFilter?: boolean
  highlightLinks?: boolean
  highlightPathToNodeId?: string
  visibleRecommendationPromoterNodeIds?: string[]
  focusedRecommendationPromoterNodeIds?: string[] | null
  onRecommendationGraphNodeClick?: (node: GraphNode, promoterNodeIds: string[] | null) => void
  onRecommendationGraphPaneClick?: () => void
}

export function ScenegraphMapPanel({
  title,
  providedData,
  showFilters = true,
  showNodeTypeFilter = true,
  highlightLinks = true,
  highlightPathToNodeId,
  visibleRecommendationPromoterNodeIds,
  focusedRecommendationPromoterNodeIds,
  onRecommendationGraphNodeClick,
  onRecommendationGraphPaneClick,
}: ScenegraphMapPanelProps) {
  const graphRef = useRef<any>(null)
  const suppressNextBackgroundClickRef = useRef(false)
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
  const hasRecommendationControls = Boolean(providedData && !showFilters)

  const graphData = useMemo<GraphData>(() => {
    const visibleNodes = showNodeTypeFilter
      ? rawGraphData.nodes.filter((node) => visibleNodeTypes.has(node.type))
      : rawGraphData.nodes
    const visibleNodeIds = new Set(visibleNodes.map((node) => node.id))
    const visibleLinks = showNodeTypeFilter
      ? rawGraphData.links.filter((link) => (
        visibleNodeIds.has(getLinkNodeId(link.source as LinkEndpoint))
        && visibleNodeIds.has(getLinkNodeId(link.target as LinkEndpoint))
      ))
      : rawGraphData.links
    const filteredLinks = visibleLinks
    const filteredNodeIds = new Set<string>()
    filteredLinks.forEach((link) => {
      filteredNodeIds.add(getLinkNodeId(link.source as LinkEndpoint))
      filteredNodeIds.add(getLinkNodeId(link.target as LinkEndpoint))
    })
    const filteredNodes = hasRecommendationControls && showNodeTypeFilter
      ? visibleNodes.filter((node) => filteredNodeIds.has(node.id))
      : visibleNodes
    return {
      centerNodeId: rawGraphData.centerNodeId,
      graphMode: rawGraphData.graphMode,
      nodes: filteredNodes,
      links: filteredLinks,
      preferredPathNodeIds: rawGraphData.preferredPathNodeIds,
      preferredPathLinkKeys: rawGraphData.preferredPathLinkKeys,
      preferredPathPromoterIdsByNodeId: rawGraphData.preferredPathPromoterIdsByNodeId,
      preferredPathPromoterIdsByLinkKey: rawGraphData.preferredPathPromoterIdsByLinkKey,
      fallbackPathNodeIds: rawGraphData.fallbackPathNodeIds,
      fallbackPathLinkKeys: rawGraphData.fallbackPathLinkKeys,
      fallbackPathPromoterIdsByNodeId: rawGraphData.fallbackPathPromoterIdsByNodeId,
      fallbackPathPromoterIdsByLinkKey: rawGraphData.fallbackPathPromoterIdsByLinkKey,
    }
  }, [
    hasRecommendationControls,
    rawGraphData,
    showNodeTypeFilter,
    visibleNodeTypes,
  ])

  // Build recommendation graph from the currently visible promoters.
  // Slider changes still reshape the graph; clicks only affect highlighting.
  const recommendationPathGraphData = useMemo<GraphData>(() => {
    if (!hasRecommendationControls || !highlightPathToNodeId) {
      return graphData
    }

    const sourceId = highlightPathToNodeId
    const sourceExists = graphData.nodes.some((node) => node.id === sourceId)
    if (!sourceExists) {
      return graphData
    }

    const targetPromoterIds = visibleRecommendationPromoterNodeIds ?? []
    if (targetPromoterIds.length === 0) {
      const sourceNode = graphData.nodes.find((node) => node.id === sourceId)
      return {
        centerNodeId: graphData.centerNodeId,
        nodes: sourceNode ? [sourceNode] : [],
        links: [],
        graphMode: graphData.graphMode,
        preferredPathNodeIds: graphData.preferredPathNodeIds,
        preferredPathLinkKeys: graphData.preferredPathLinkKeys,
        preferredPathPromoterIdsByNodeId: graphData.preferredPathPromoterIdsByNodeId,
        preferredPathPromoterIdsByLinkKey: graphData.preferredPathPromoterIdsByLinkKey,
        fallbackPathNodeIds: graphData.fallbackPathNodeIds,
        fallbackPathLinkKeys: graphData.fallbackPathLinkKeys,
        fallbackPathPromoterIdsByNodeId: graphData.fallbackPathPromoterIdsByNodeId,
        fallbackPathPromoterIdsByLinkKey: graphData.fallbackPathPromoterIdsByLinkKey,
      }
    }

    const nodeTypeById = new Map<string, NodeType>()
    graphData.nodes.forEach((node) => nodeTypeById.set(node.id, node.type))

    const includedNodeIds = new Set<string>([sourceId])
    const includedLinkKeys = new Set<string>()

    const collectBackendPath = (
      promoterNodeId: string,
      nodeIdsByPromoter?: Record<string, string[]>,
      linkKeysByPromoter?: Record<string, string[]>,
    ): boolean => {
      const nodeIds = nodeIdsByPromoter?.[promoterNodeId] ?? []
      const linkKeys = linkKeysByPromoter?.[promoterNodeId] ?? []
      if (nodeIds.length === 0 || linkKeys.length === 0) return false
      nodeIds.forEach((nodeId) => includedNodeIds.add(nodeId))
      linkKeys.forEach((linkKey) => includedLinkKeys.add(linkKey))
      return true
    }

    targetPromoterIds.forEach((targetPromoterId) => {
      if (!graphData.nodes.some((node) => node.id === targetPromoterId)) return
      collectBackendPath(
        targetPromoterId,
        graphData.fallbackPathNodeIds,
        graphData.fallbackPathLinkKeys,
      )
    })

    const pathEventIds = new Set(
      Array.from(includedNodeIds).filter((nodeId) => nodeTypeById.get(nodeId) === 'event')
    )
    graphData.links.forEach((link) => {
      const source = getLinkNodeId(link.source as LinkEndpoint)
      const target = getLinkNodeId(link.target as LinkEndpoint)
      const sourceType = nodeTypeById.get(source)
      const targetType = nodeTypeById.get(target)
      const eventId = sourceType === 'event' && targetType === 'venue'
        ? source
        : (targetType === 'event' && sourceType === 'venue' ? target : null)
      if (!eventId || !pathEventIds.has(eventId)) return
      includedNodeIds.add(source)
      includedNodeIds.add(target)
      includedLinkKeys.add(getUndirectedLinkKey(source, target))
    })

    const nodes = graphData.nodes.filter((node) => includedNodeIds.has(node.id))
    const links = graphData.links.filter((link) => {
      const source = getLinkNodeId(link.source as LinkEndpoint)
      const target = getLinkNodeId(link.target as LinkEndpoint)
      return includedLinkKeys.has(getUndirectedLinkKey(source, target))
    })

    return {
      centerNodeId: graphData.centerNodeId,
      nodes,
      links,
      graphMode: graphData.graphMode,
      preferredPathNodeIds: graphData.preferredPathNodeIds,
      preferredPathLinkKeys: graphData.preferredPathLinkKeys,
      preferredPathPromoterIdsByNodeId: graphData.preferredPathPromoterIdsByNodeId,
      preferredPathPromoterIdsByLinkKey: graphData.preferredPathPromoterIdsByLinkKey,
      fallbackPathNodeIds: graphData.fallbackPathNodeIds,
      fallbackPathLinkKeys: graphData.fallbackPathLinkKeys,
      fallbackPathPromoterIdsByNodeId: graphData.fallbackPathPromoterIdsByNodeId,
      fallbackPathPromoterIdsByLinkKey: graphData.fallbackPathPromoterIdsByLinkKey,
    }
  }, [
    graphData,
    hasRecommendationControls,
    highlightPathToNodeId,
    visibleRecommendationPromoterNodeIds,
  ])

  // Resolve graph node ownership with backend reverse path indexes.
  const resolvePromoterNodesForRecommendationNode = useCallback((nodeId: string): string[] | null => {
    if (!highlightPathToNodeId) return null
    if (nodeId === highlightPathToNodeId) return null
    if (nodeId.startsWith('promoter-')) return [nodeId]

    const promoterCandidates = visibleRecommendationPromoterNodeIds ?? []
    const ownerPromoterIds = recommendationPathGraphData.fallbackPathPromoterIdsByNodeId?.[nodeId] ?? []
    return ownerPromoterIds.filter((promoterId) => promoterCandidates.includes(promoterId))
  }, [
    highlightPathToNodeId,
    recommendationPathGraphData.fallbackPathPromoterIdsByNodeId,
    visibleRecommendationPromoterNodeIds,
  ])

  const pathSourceNode = highlightPathToNodeId
    ? (recommendationPathGraphData.nodes.find((node) => node.id === highlightPathToNodeId) ?? null)
    : null
  const pathTargetPromoterIds = focusedRecommendationPromoterNodeIds?.length
    ? focusedRecommendationPromoterNodeIds
    : []
  const { pathLinks, pathNodeIds } = useGraphHighlights(
    pathSourceNode,
    recommendationPathGraphData,
    highlightPathToNodeId ? pathTargetPromoterIds : undefined,
  )
  const isPathFocusActive = Boolean(highlightPathToNodeId && pathTargetPromoterIds.length > 0 && pathLinks.size > 0)
  const recommendationSourceNodeId = highlightPathToNodeId ?? null
  const highlightedPathNodeIds = useMemo(() => {
    if (!isPathFocusActive) return pathNodeIds

    const nextHighlightedNodeIds = new Set(pathNodeIds)
    const nodeTypeById = new Map<string, NodeType>()
    recommendationPathGraphData.nodes.forEach((node) => {
      nodeTypeById.set(node.id, node.type)
    })

    const pathEventIds = new Set(
      Array.from(nextHighlightedNodeIds).filter((nodeId) => nodeTypeById.get(nodeId) === 'event')
    )

    recommendationPathGraphData.links.forEach((link) => {
      const source = getLinkNodeId(link.source as LinkEndpoint)
      const target = getLinkNodeId(link.target as LinkEndpoint)
      const sourceType = nodeTypeById.get(source)
      const targetType = nodeTypeById.get(target)
      const eventId = sourceType === 'event' && targetType === 'venue'
        ? source
        : (targetType === 'event' && sourceType === 'venue' ? target : null)
      if (!eventId || !pathEventIds.has(eventId)) return
      nextHighlightedNodeIds.add(source)
      nextHighlightedNodeIds.add(target)
    })

    return nextHighlightedNodeIds
  }, [isPathFocusActive, pathNodeIds, recommendationPathGraphData.links, recommendationPathGraphData.nodes])
  useGraphPhysics(graphRef, recommendationPathGraphData)

  useEffect(() => {
    if (providedData) return
    if (!selectedType || selectedEntityId === null || !data) return

    const nextSelectedNode = data.nodes.find((node) => (
      node.type === selectedType && node.entityId === selectedEntityId
    ))
    if (nextSelectedNode && selectedNode?.id !== nextSelectedNode.id) {
      setSelected(nextSelectedNode)
    }
  }, [data, providedData, selectedEntityId, selectedNode?.id, selectedType, setSelected])

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
      if (providedData) {
        suppressNextBackgroundClickRef.current = true
        window.setTimeout(() => {
          suppressNextBackgroundClickRef.current = false
        }, 0)
        if (highlightPathToNodeId && onRecommendationGraphNodeClick) {
          const resolvedPromoterNodeIds = resolvePromoterNodesForRecommendationNode(nextNode.id)
          onRecommendationGraphNodeClick(nextNode, resolvedPromoterNodeIds)
        } else {
          setSelected(nextNode)
        }
        return
      }
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
    [
      highlightPathToNodeId,
      onRecommendationGraphNodeClick,
      providedData,
      resolvePromoterNodesForRecommendationNode,
      searchParams,
      selectedEntityId,
      selectedNode?.id,
      selectedType,
      setSearchParams,
      setSelected,
    ]
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
  const nodeCount = recommendationPathGraphData.nodes.length
  const linkCount = recommendationPathGraphData.links.length
  const displayedEventDates = recommendationPathGraphData.nodes
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
    isPathFocusActive
      ? pathLinks.has(getUndirectedLinkKey(source, target))
      : false
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
        {showNodeTypeFilter && (
          <GraphNodeFilter visibleNodeTypes={visibleNodeTypes} onToggle={handleLegendToggle} />
        )}
        <ForceGraph2D
          ref={graphRef}
          width={graphSize.width || undefined}
          height={graphSize.height || undefined}
          graphData={recommendationPathGraphData}
          nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D) => {
            const isHighlightedNode = isPathFocusActive
              ? (node.id === recommendationSourceNodeId || highlightedPathNodeIds.has(node.id))
              : true
            drawNodeShape(
              ctx,
              node.x,
              node.y,
              5,
              node.type,
              selectedNode?.id === node.id || node.id === recommendationSourceNodeId,
              isHighlightedNode ? 1 : 0.16,
            )
          }}
          nodeColor={() => 'transparent'}
          nodeRelSize={3}
          nodeVal={(n: any) => (selectedNode?.id === n.id ? 3 : 1)}
          nodeLabel={(n: any) => n.name ?? n.label ?? n.id}
          linkWidth={(l: any) => {
            const source = typeof l.source === 'object' ? l.source.id : l.source
            const target = typeof l.target === 'object' ? l.target.id : l.target
            const linkStrength = getLinkStrengthValue(l)
            const baseWidth = 0.35 + Math.min(linkStrength, 1) * 1.25
            if (highlightLinks && isHighlightedLink(source, target)) {
              return baseWidth * 1.85
            }
            return baseWidth
          }}
          linkLineDash={(l: any) => getLinkDashPattern(l)}
          linkColor={(l: any) => {
            const source = typeof l.source === 'object' ? l.source.id : l.source
            const target = typeof l.target === 'object' ? l.target.id : l.target
            if (highlightLinks && isHighlightedLink(source, target)) {
              return hexToRgba(linkHighlight, 0.86)
            }
            return hexToRgba(linkDim, 0.52)
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
          onBackgroundClick={() => {
            if (suppressNextBackgroundClickRef.current) return
            if (providedData && onRecommendationGraphPaneClick) {
              onRecommendationGraphPaneClick()
            }
          }}
          backgroundColor={graphBackground}
          warmupTicks={120}
          cooldownTicks={180}
        />
      </div>
    </section>
  )
}
