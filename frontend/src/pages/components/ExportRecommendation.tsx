import { useCallback, useMemo, useState } from 'react'
import type { PromoterRecommendation, PromoterRecommendationResponse } from '../../types/recommendation'

type RecommendationGraphMode = 'compact' | 'full'

interface RecommendationExportMenuProps {
  recommendationsData: PromoterRecommendationResponse | null
  filteredRecommendations: PromoterRecommendation[]
  recommendationStrengthThreshold: number
  recommendationGraphMode: RecommendationGraphMode
}

const MORE_SUFFIX_PATTERN = /,?\s*\+\d+\s+more\.?$/i
const PROMOTER_SIZE_LABELS: Record<'small' | 'medium' | 'large', string> = {
  small: 'Small',
  medium: 'Medium',
  large: 'Large',
}

function recommendationScore(recommendation: PromoterRecommendation): number {
  const directScore = recommendation.score
  if (typeof directScore === 'number' && Number.isFinite(directScore)) {
    return Math.max(0, Math.min(1, directScore))
  }

  const debugTotal = recommendation.debug?.weightedScores?.total
  if (typeof debugTotal === 'number' && Number.isFinite(debugTotal)) {
    return Math.max(0, Math.min(1, debugTotal))
  }

  return 0
}

function downloadTextFile(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

function csvCell(value: unknown): string {
  const text = Array.isArray(value) ? value.join('; ') : String(value ?? '')
  return `"${text.replaceAll('"', '""')}"`
}

function htmlEscape(value: unknown): string {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function sourceArtistName(recommendationsData: PromoterRecommendationResponse): string {
  const sourceNode = [
    ...recommendationsData.graph.nodes,
    ...(recommendationsData.analyticsGraph?.nodes ?? []),
  ].find((node) => (
    node.type === 'artist' && node.entityId === recommendationsData.entityId
  ))

  return sourceNode?.name ?? `Artist ${recommendationsData.entityId}`
}

export function RecommendationExportMenu({
  recommendationsData,
  filteredRecommendations,
  recommendationStrengthThreshold,
  recommendationGraphMode,
}: RecommendationExportMenuProps) {
  const [isExportMenuOpen, setIsExportMenuOpen] = useState(false)
  const exportRecommendations = useMemo(() => {
    if (!recommendationsData) return []

    return [...recommendationsData.recommendations].sort((left, right) => {
      const scoreDelta = recommendationScore(right) - recommendationScore(left)
      if (Math.abs(scoreDelta) > 1e-9) return scoreDelta
      return left.name.localeCompare(right.name)
    })
  }, [recommendationsData])

  const handleExportJson = useCallback(() => {
    if (!recommendationsData) return
    setIsExportMenuOpen(false)

    downloadTextFile(
      `promoter-recommendations-artist-${recommendationsData.entityId}.json`,
      JSON.stringify({
        exportedAt: new Date().toISOString(),
        threshold: recommendationStrengthThreshold,
        graphMode: recommendationGraphMode,
        visibleRecommendationIds: filteredRecommendations.map((recommendation) => recommendation.id),
        data: recommendationsData,
      }, null, 2),
      'application/json;charset=utf-8',
    )
  }, [
    filteredRecommendations,
    recommendationGraphMode,
    recommendationStrengthThreshold,
    recommendationsData,
  ])

  const handleExportCsv = useCallback(() => {
    if (!recommendationsData) return
    setIsExportMenuOpen(false)

    const rows = exportRecommendations.map((recommendation, index) => [
      index + 1,
      recommendation.name,
      `${Math.round(recommendationScore(recommendation) * 100)}%`,
      PROMOTER_SIZE_LABELS[recommendation.promoterSizeSegment],
      recommendation.reasons
        .map((reason) => reason.replace(MORE_SUFFIX_PATTERN, ''))
        .join(' | '),
    ])
    const header = ['rank', 'promoter', 'score', 'size', 'reasons']
    const csv = [header, ...rows]
      .map((row) => row.map(csvCell).join(','))
      .join('\n')

    downloadTextFile(
      `promoter-recommendations-artist-${recommendationsData.entityId}.csv`,
      csv,
      'text/csv;charset=utf-8',
    )
  }, [exportRecommendations, recommendationsData])

  const handleExportPdf = useCallback(() => {
    if (!recommendationsData) return
    setIsExportMenuOpen(false)

    const artistName = sourceArtistName(recommendationsData)
    const reportRows = exportRecommendations.map((recommendation, index) => {
      const reasons = recommendation.reasons
        .map((reason) => `<li>${htmlEscape(reason.replace(MORE_SUFFIX_PATTERN, ''))}</li>`)
        .join('')
      return `
        <article class="recommendation">
          <h2>${index + 1}. ${htmlEscape(recommendation.name)}</h2>
          <p><strong>Score:</strong> ${Math.round(recommendationScore(recommendation) * 100)}% &nbsp; <strong>Size:</strong> ${htmlEscape(PROMOTER_SIZE_LABELS[recommendation.promoterSizeSegment])}</p>
          <ul>${reasons}</ul>
        </article>
      `
    }).join('')
    const popup = window.open('', '_blank')
    if (!popup) return

    popup.document.write(`
      <!doctype html>
      <html>
        <head>
          <title>Promoter Recommendations</title>
          <style>
            body { color: #1f2724; font-family: Arial, sans-serif; line-height: 1.45; margin: 32px; }
            h1 { font-size: 24px; margin: 0 0 8px; }
            .meta { color: #60706a; margin: 0 0 24px; }
            .recommendation { border-top: 1px solid #d8dfdc; break-inside: avoid; padding: 16px 0; }
            h2 { font-size: 17px; margin: 0 0 6px; }
            p { margin: 0 0 8px; }
            ul { margin: 8px 0 0 18px; padding: 0; }
            li { margin: 4px 0; }
            @page { margin: 18mm; }
          </style>
        </head>
        <body>
          <h1>Promoter Recommendations</h1>
          <p class="meta">
            Artist ${htmlEscape(artistName)} ·
            ${exportRecommendations.length} recommendations exported ·
            exported ${htmlEscape(new Date().toLocaleString())}
          </p>
          ${reportRows}
        </body>
      </html>
    `)
    popup.document.close()
    popup.focus()
    window.setTimeout(() => {
      popup.print()
    }, 250)
  }, [exportRecommendations, recommendationsData])

  return (
    <div className="export-menu">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={isExportMenuOpen}
        disabled={!recommendationsData}
        onClick={() => setIsExportMenuOpen((isOpen) => !isOpen)}
      >
        Export
      </button>
      {isExportMenuOpen && recommendationsData && (
        <div className="export-menu-list" role="menu" aria-label="Export recommendations">
          <button type="button" role="menuitem" onClick={handleExportJson}>JSON</button>
          <button type="button" role="menuitem" onClick={handleExportCsv}>CSV</button>
          <button type="button" role="menuitem" onClick={handleExportPdf}>PDF</button>
        </div>
      )}
    </div>
  )
}
