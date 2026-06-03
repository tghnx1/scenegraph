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
const EGO_GRAPH_CENTER_RETRIES = 24
const EGO_GRAPH_CENTER_RETRY_MS = 80
const EGO_GRAPH_CENTER_DURATION_MS = 520
const EGO_GRAPH_ZOOM = 1.35
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

function hasGraphPosition(node: GraphNode): node is GraphNode & { x: number; y: number } {
  const positionedNode = node as GraphNode & { x?: unknown; y?: unknown }
  return typeof positionedNode.x === 'number' && Number.isFinite(positionedNode.x)
    && typeof positionedNode.y === 'number' && Number.isFinite(positionedNode.y)
}

interface ScenegraphMapPanelProps {
  title?: string
  providedData?: GraphData
  showFilters?: boolean
  highlightLinks?: boolean
  highlightPathToNodeId?: string
  visibleRecommendationPromoterNodeIds?: string[]
  focusedRecommendationPromoterNodeId?: string | null
  onRecommendationGraphNodeClick?: (node: GraphNode, promoterNodeId: string | null) => void
}

export function ScenegraphMapPanel({
  title,
  providedData,
  showFilters = true,
  highlightLinks = true,
  highlightPathToNodeId,
  visibleRecommendationPromoterNodeIds,
  focusedRecommendationPromoterNodeId,
  onRecommendationGraphNodeClick,
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
  const hasRecommendationControls = Boolean(providedData && !showFilters)

  const graphData = useMemo<GraphData>(() => {
    const visibleNodes = rawGraphData.nodes.filter((node) => visibleNodeTypes.has(node.type))
    const visibleNodeIds = new Set(visibleNodes.map((node) => node.id))
    const visibleLinks = rawGraphData.links.filter((link) => (
      visibleNodeIds.has(getLinkNodeId(link.source as LinkEndpoint))
      && visibleNodeIds.has(getLinkNodeId(link.target as LinkEndpoint))
    ))
    const filteredLinks = visibleLinks
    const filteredNodeIds = new Set<string>()
    filteredLinks.forEach((link) => {
      filteredNodeIds.add(getLinkNodeId(link.source as LinkEndpoint))
      filteredNodeIds.add(getLinkNodeId(link.target as LinkEndpoint))
    })
    const filteredNodes = hasRecommendationControls
      ? visibleNodes.filter((node) => filteredNodeIds.has(node.id))
      : visibleNodes
    return {
      centerNodeId: rawGraphData.centerNodeId,
      nodes: filteredNodes,
      links: filteredLinks,
      promoterPathNodeIds: rawGraphData.promoterPathNodeIds,
      promoterPathLinkKeys: rawGraphData.promoterPathLinkKeys,
    }
  }, [
    hasRecommendationControls,
    rawGraphData,
    visibleNodeTypes,
  ])

  // Build minimal recommendation subgraph as a union of shortest artist->promoter paths.
  const recommendationPathGraphData = useMemo<GraphData>(() => {
    if (!hasRecommendationControls || !highlightPathToNodeId) {
      return graphData
    }

    const sourceId = highlightPathToNodeId
    const sourceExists = graphData.nodes.some((node) => node.id === sourceId)
    if (!sourceExists) {
      return graphData
    }

    const focusedPromoterId = focusedRecommendationPromoterNodeId
    const targetPromoterIds = focusedPromoterId
      ? [focusedPromoterId]
      : (visibleRecommendationPromoterNodeIds ?? [])

    if (targetPromoterIds.length === 0) {
      const sourceNode = graphData.nodes.find((node) => node.id === sourceId)
      return {
        centerNodeId: graphData.centerNodeId,
        nodes: sourceNode ? [sourceNode] : [],
        links: [],
      }
    }

    const adjacency = new Map<string, Set<string>>()
    const adjacencyWithLinks = new Map<string, Array<{ neighborId: string; link: GraphData['links'][number] }>>()
    const nodeTypeById = new Map<string, NodeType>()
    graphData.nodes.forEach((node) => nodeTypeById.set(node.id, node.type))
    graphData.links.forEach((link) => {
      const source = getLinkNodeId(link.source as LinkEndpoint)
      const target = getLinkNodeId(link.target as LinkEndpoint)
      if (!adjacency.has(source)) adjacency.set(source, new Set<string>())
      if (!adjacency.has(target)) adjacency.set(target, new Set<string>())
      adjacency.get(source)?.add(target)
      adjacency.get(target)?.add(source)
      if (!adjacencyWithLinks.has(source)) adjacencyWithLinks.set(source, [])
      if (!adjacencyWithLinks.has(target)) adjacencyWithLinks.set(target, [])
      adjacencyWithLinks.get(source)?.push({ neighborId: target, link })
      adjacencyWithLinks.get(target)?.push({ neighborId: source, link })
    })

    const includedNodeIds = new Set<string>([sourceId])
    const includedLinkKeys = new Set<string>()

    // Collect a single shortest source->target path for compact baseline graph rendering.
    const collectPath = (targetId: string) => {
      if (targetId === sourceId) return
      if (!adjacency.has(targetId)) return

      const queue: string[] = [sourceId]
      const visited = new Set<string>([sourceId])
      const previous = new Map<string, string>()

      while (queue.length > 0 && !visited.has(targetId)) {
        const currentId = queue.shift()!
        const neighbors = adjacency.get(currentId)
        if (!neighbors) continue

        for (const neighborId of neighbors) {
          if (visited.has(neighborId)) continue
          visited.add(neighborId)
          previous.set(neighborId, currentId)
          queue.push(neighborId)
        }
      }

      if (!visited.has(targetId)) return

      let currentId = targetId
      includedNodeIds.add(currentId)
      while (currentId !== sourceId) {
        const priorId = previous.get(currentId)
        if (!priorId) break
        includedNodeIds.add(priorId)
        includedLinkKeys.add(getUndirectedLinkKey(priorId, currentId))
        currentId = priorId
      }
    }

    // Use backend-precomputed preferred paths for focused promoter rendering.
    const collectBackendPreferredPath = (targetId: string): boolean => {
      const nodeIds = graphData.promoterPathNodeIds?.[targetId] ?? []
      const linkKeys = graphData.promoterPathLinkKeys?.[targetId] ?? []
      if (nodeIds.length === 0 || linkKeys.length === 0) return false
      nodeIds.forEach((nodeId) => includedNodeIds.add(nodeId))
      linkKeys.forEach((linkKey) => includedLinkKeys.add(linkKey))
      return true
    }

    // Collect top-K strongest source->target paths (bounded-depth simple paths).
    const collectStrongestPaths = (
      targetId: string,
      {
        topK,
        maxDepth,
        maxCandidates,
      }: {
        topK: number
        maxDepth: number
        maxCandidates: number
      },
    ): boolean => {
      if (targetId === sourceId) return false
      if (!adjacencyWithLinks.has(targetId)) return false

      const candidates: Array<{ nodeIds: string[]; linkKeys: string[]; totalStrength: number }> = []
      const pathNodes = new Set<string>([sourceId])
      const pathNodeIds = [sourceId]
      const pathLinkKeys: string[] = []
      const pathLinks: GraphData['links'][number][] = []

      const dfs = (currentId: string, depth: number) => {
        if (candidates.length >= maxCandidates) return
        if (depth > maxDepth) return
        if (currentId === targetId) {
          const totalStrength = pathLinks.reduce((sum, link) => sum + getLinkStrengthValue(link), 0)
          candidates.push({ nodeIds: [...pathNodeIds], linkKeys: [...pathLinkKeys], totalStrength })
          return
        }

        const neighbors = adjacencyWithLinks.get(currentId) ?? []
        for (const { neighborId, link } of neighbors) {
          const neighborType = nodeTypeById.get(neighborId)
          if (neighborType === 'venue') continue
          if (neighborType === 'promoter' && neighborId !== targetId) continue
          if (pathNodes.has(neighborId)) continue

          pathNodes.add(neighborId)
          pathNodeIds.push(neighborId)
          pathLinkKeys.push(getUndirectedLinkKey(currentId, neighborId))
          pathLinks.push(link)
          dfs(neighborId, depth + 1)
          pathLinks.pop()
          pathLinkKeys.pop()
          pathNodeIds.pop()
          pathNodes.delete(neighborId)
          if (candidates.length >= maxCandidates) return
        }
      }

      dfs(sourceId, 0)
      if (candidates.length === 0) return false

      const uniqueCandidates = new Map<string, { nodeIds: string[]; linkKeys: string[]; totalStrength: number }>()
      for (const candidate of candidates) {
        const signature = candidate.linkKeys.slice().sort().join('|')
        const existing = uniqueCandidates.get(signature)
        if (!existing || candidate.totalStrength > existing.totalStrength) {
          uniqueCandidates.set(signature, candidate)
        }
      }

      const strongest = Array.from(uniqueCandidates.values())
        .sort((left, right) => {
          const strengthDelta = right.totalStrength - left.totalStrength
          if (Math.abs(strengthDelta) > 1e-9) return strengthDelta
          return left.linkKeys.length - right.linkKeys.length
        })
        .slice(0, topK)

      strongest.forEach((path) => {
        path.nodeIds.forEach((nodeId) => includedNodeIds.add(nodeId))
        path.linkKeys.forEach((linkKey) => includedLinkKeys.add(linkKey))
      })
      return strongest.length > 0
    }

    targetPromoterIds.forEach((targetPromoterId) => {
      if (graphData.nodes.some((node) => node.id === targetPromoterId)) {
        if (focusedPromoterId) {
          const foundPreferredPath = collectBackendPreferredPath(targetPromoterId)
          if (foundPreferredPath) return

          const foundStrongestPaths = collectStrongestPaths(
            targetPromoterId,
            {
              topK: 3,
              maxDepth: 6,
              maxCandidates: 800,
            },
          )
          if (!foundStrongestPaths) collectPath(targetPromoterId)
        } else {
          collectPath(targetPromoterId)
        }
      }
    })

    // Keep venue context for events that are already part of the selected path.
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
    }
  }, [
    focusedRecommendationPromoterNodeId,
    graphData,
    hasRecommendationControls,
    highlightPathToNodeId,
    visibleRecommendationPromoterNodeIds,
  ])

  // Resolve a shortest path node set for source->target in the current recommendation graph.
  const getPathNodeIds = useCallback((sourceId: string, targetId: string): Set<string> => {
    const adjacency = new Map<string, Set<string>>()
    recommendationPathGraphData.links.forEach((link) => {
      const source = getLinkNodeId(link.source as LinkEndpoint)
      const target = getLinkNodeId(link.target as LinkEndpoint)
      if (!adjacency.has(source)) adjacency.set(source, new Set<string>())
      if (!adjacency.has(target)) adjacency.set(target, new Set<string>())
      adjacency.get(source)?.add(target)
      adjacency.get(target)?.add(source)
    })

    const queue: string[] = [sourceId]
    const visited = new Set<string>(queue)
    const previous = new Map<string, string>()

    while (queue.length > 0 && !visited.has(targetId)) {
      const currentId = queue.shift()!
      const neighbors = adjacency.get(currentId)
      if (!neighbors) continue
      for (const neighborId of neighbors) {
        if (visited.has(neighborId)) continue
        visited.add(neighborId)
        previous.set(neighborId, currentId)
        queue.push(neighborId)
      }
    }

    if (!visited.has(targetId)) return new Set<string>()

    const pathNodeIds = new Set<string>([targetId])
    let currentId = targetId
    while (currentId !== sourceId) {
      const priorId = previous.get(currentId)
      if (!priorId) return new Set<string>()
      pathNodeIds.add(priorId)
      currentId = priorId
    }

    return pathNodeIds
  }, [recommendationPathGraphData.links])

  // Choose which promoter path a clicked recommendation-graph node belongs to.
  const resolvePromoterNodeForRecommendationNode = useCallback((nodeId: string): string | null => {
    if (!highlightPathToNodeId) return null
    if (nodeId.startsWith('promoter-')) return nodeId

    const sourceId = highlightPathToNodeId
    const promoterCandidates = focusedRecommendationPromoterNodeId
      ? [focusedRecommendationPromoterNodeId]
      : (visibleRecommendationPromoterNodeIds ?? [])

    for (const promoterId of promoterCandidates) {
      const pathNodes = getPathNodeIds(sourceId, promoterId)
      if (pathNodes.has(nodeId)) {
        return promoterId
      }
    }

    return null
  }, [
    focusedRecommendationPromoterNodeId,
    getPathNodeIds,
    highlightPathToNodeId,
    visibleRecommendationPromoterNodeIds,
  ])

  const pathSelectedPromoter = focusedRecommendationPromoterNodeId
    ? recommendationPathGraphData.nodes.find((node) => node.id === focusedRecommendationPromoterNodeId) ?? null
    : null
  const { connectedNodes, pathLinks, pathNodeIds } = useGraphHighlights(
    pathSelectedPromoter,
    recommendationPathGraphData,
    highlightPathToNodeId,
  )
  useGraphPhysics(graphRef, recommendationPathGraphData)

  useEffect(() => {
    if (providedData || !selectedType || !selectedId || graphSize.width === 0 || graphSize.height === 0) return

    const centerNodeId = recommendationPathGraphData.centerNodeId
    if (!centerNodeId) return

    let timeoutId: number | undefined
    let isCancelled = false

    const centerWhenReady = (attempt: number) => {
      if (isCancelled) return

      const graph = graphRef.current
      const centerNode = recommendationPathGraphData.nodes.find((node) => node.id === centerNodeId)

      if (graph && centerNode && hasGraphPosition(centerNode)) {
        graph.centerAt(centerNode.x, centerNode.y, EGO_GRAPH_CENTER_DURATION_MS)
        graph.zoom(EGO_GRAPH_ZOOM, EGO_GRAPH_CENTER_DURATION_MS)
        return
      }

      if (attempt < EGO_GRAPH_CENTER_RETRIES) {
        timeoutId = window.setTimeout(
          () => centerWhenReady(attempt + 1),
          EGO_GRAPH_CENTER_RETRY_MS,
        )
      }
    }

    centerWhenReady(0)

    return () => {
      isCancelled = true
      if (timeoutId !== undefined) window.clearTimeout(timeoutId)
    }
  }, [
    graphSize.height,
    graphSize.width,
    providedData,
    recommendationPathGraphData,
    selectedId,
    selectedType,
  ])

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
        if (highlightPathToNodeId && onRecommendationGraphNodeClick) {
          const resolvedPromoterNodeId = resolvePromoterNodeForRecommendationNode(nextNode.id)
          onRecommendationGraphNodeClick(nextNode, resolvedPromoterNodeId)
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
      resolvePromoterNodeForRecommendationNode,
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
  const isPathFocusActive = Boolean(pathSelectedPromoter && highlightPathToNodeId && pathLinks.size > 0)
  const focusedSubgraphNodeIds = useMemo(() => {
    if (!isPathFocusActive) return null
    return new Set(recommendationPathGraphData.nodes.map((node) => node.id))
  }, [isPathFocusActive, recommendationPathGraphData.nodes])
  const focusedSubgraphLinkKeys = useMemo(() => {
    if (!isPathFocusActive) return null
    const keys = new Set<string>()
    recommendationPathGraphData.links.forEach((link) => {
      const source = getLinkNodeId(link.source as LinkEndpoint)
      const target = getLinkNodeId(link.target as LinkEndpoint)
      keys.add(getUndirectedLinkKey(source, target))
    })
    return keys
  }, [isPathFocusActive, recommendationPathGraphData.links])
  const isHighlightedLink = (source: string, target: string) => (
    highlightPathToNodeId
      ? (pathSelectedPromoter
          ? (
            focusedSubgraphLinkKeys?.has(getUndirectedLinkKey(source, target))
            ?? pathLinks.has(getUndirectedLinkKey(source, target))
          )
          : true)
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
        {!hasRecommendationControls && (
          <GraphNodeFilter visibleNodeTypes={visibleNodeTypes} onToggle={handleLegendToggle} />
        )}
        <ForceGraph2D
          ref={graphRef}
          width={graphSize.width || undefined}
          height={graphSize.height || undefined}
          graphData={recommendationPathGraphData}
          nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D) => {
            const isHighlightedNode = isPathFocusActive
              ? (focusedSubgraphNodeIds?.has(node.id) ?? pathNodeIds.has(node.id))
              : true
            drawNodeShape(
              ctx,
              node.x,
              node.y,
              5,
              node.type,
              selectedNode?.id === node.id,
              isHighlightedNode ? 1 : 0.048,
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
            if (isPathFocusActive) {
              return Math.max(baseWidth * 0.2, 0.14)
            }
            return baseWidth
          }}
          linkColor={(l: any) => {
            const source = typeof l.source === 'object' ? l.source.id : l.source
            const target = typeof l.target === 'object' ? l.target.id : l.target
            if (highlightLinks && isHighlightedLink(source, target)) {
              return hexToRgba(linkHighlight, 0.86)
            }
            if (isPathFocusActive) {
              return hexToRgba(linkDim, 0.056)
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
          backgroundColor={graphBackground}
          warmupTicks={120}
          cooldownTicks={180}
        />
      </div>
    </section>
  )
}
