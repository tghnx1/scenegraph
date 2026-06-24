import {useCallback} from 'react'
import {csvCell, downloadTextFile, htmlEscape, printHtmlDocument} from '@/shared/lib/export'
import {ExportMenu} from '@/shared/ui/export-menu'
import type {DashboardEntity, DashboardStatus} from '../../types/dashboardComposition'
import type {DashboardMetrics} from '../../types/dashboardMetrics'

interface DashboardExportMenuProps {
  dashboardStatus: DashboardStatus | null
  dashboardMetrics: DashboardMetrics | null
  selectedEntities: DashboardEntity[]
  dateFrom: string
  dateTo: string
}

function formatExportValue(value: number | string | null | undefined) {
  return value ?? '-'
}

export function DashboardExportMenu({
  dashboardStatus,
  dashboardMetrics,
  selectedEntities,
  dateFrom,
  dateTo,
}: DashboardExportMenuProps) {
  const handleExportJson = useCallback(() => {
    if (!dashboardStatus && !dashboardMetrics) return
    downloadTextFile(
      'dashboard-report.json',
      JSON.stringify({
        exportedAt: new Date().toISOString(),
        filters: {include: selectedEntities, dateFrom: dateFrom || null, dateTo: dateTo || null},
        data: {
          composition: dashboardStatus,
          metrics: dashboardMetrics,
        },
      }, null, 2),
      'application/json;charset=utf-8',
    )
  }, [dashboardMetrics, dashboardStatus, dateFrom, dateTo, selectedEntities])

  const handleExportCsv = useCallback(() => {
    if (!dashboardStatus && !dashboardMetrics) return
    const compositionRows = dashboardStatus?.items.map((item) => [
      item.id,
      item.label,
      item.value,
      item.percentage,
      dashboardStatus.from,
      dashboardStatus.to,
    ]) ?? []
    const metricRows = dashboardMetrics?.metrics.map((metric) => [
      metric.id,
      metric.label,
      metric.value,
      metric.total,
      metric.percentage,
      metric.status,
      metric.meaning,
      metric.whyItMatters,
      metric.fix,
    ]) ?? []
    const rankingRows = dashboardMetrics?.rankings.flatMap((ranking) =>
      ranking.items.map((item, index) => [
        ranking.id,
        ranking.label,
        index + 1,
        item.id ?? '',
        item.name ?? item.label ?? '',
        item.value ?? item.count ?? '',
      ]),
    ) ?? []
    const csvSections = [
      ['composition'],
      ['entity', 'label', 'value', 'percentage', 'from', 'to'],
      ...compositionRows,
      [],
      ['metrics'],
      ['id', 'label', 'value', 'total', 'percentage', 'status', 'meaning', 'why_it_matters', 'fix'],
      ...metricRows,
      [],
      ['rankings'],
      ['ranking_id', 'ranking_label', 'rank', 'item_id', 'item_label', 'value'],
      ...rankingRows,
    ].map((row) => row.map(csvCell).join(',')).join('\n')
    downloadTextFile('dashboard-report.csv', csvSections, 'text/csv;charset=utf-8')
  }, [dashboardMetrics, dashboardStatus])

  const handleExportPdf = useCallback(() => {
    if (!dashboardStatus && !dashboardMetrics) return
    const compositionRows = dashboardStatus?.items.map((item) => `
      <tr>
        <td>${htmlEscape(item.label)}</td>
        <td>${htmlEscape(item.value.toLocaleString())}</td>
        <td>${htmlEscape(item.percentage.toFixed(2))}%</td>
      </tr>
    `).join('') ?? ''
    const metricRows = dashboardMetrics?.metrics.map((metric) => `
      <tr>
        <td>${htmlEscape(metric.label)}</td>
        <td>${htmlEscape(formatExportValue(metric.value))}</td>
        <td>${htmlEscape(formatExportValue(metric.total))}</td>
        <td>${htmlEscape(formatExportValue(metric.percentage))}</td>
        <td>${htmlEscape(metric.status)}</td>
      </tr>
    `).join('') ?? ''
    const rankingRows = dashboardMetrics?.rankings.flatMap((ranking) =>
      ranking.items.map((item, index) => `
        <tr>
          <td>${htmlEscape(ranking.label)}</td>
          <td>${htmlEscape(index + 1)}</td>
          <td>${htmlEscape(item.name ?? item.label ?? item.id ?? '-')}</td>
          <td>${htmlEscape(formatExportValue(item.value ?? item.count))}</td>
        </tr>
      `),
    ).join('') ?? ''
    printHtmlDocument(`
      <!doctype html>
      <html>
        <head>
          <title>Dashboard Report</title>
          <style>
            body { color: #1f2724; font-family: Arial, sans-serif; margin: 32px; }
            h1 { margin-bottom: 8px; }
            .meta { color: #60706a; margin-bottom: 24px; }
            h2 { margin-top: 28px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border-bottom: 1px solid #d8dfdc; padding: 10px; text-align: left; }
            th { background: #f2f5f3; }
            @page { margin: 18mm; }
          </style>
        </head>
        <body>
          <h1>Dashboard Report</h1>
          <p class="meta">
            ${htmlEscape(dashboardStatus?.from ?? '-')} to ${htmlEscape(dashboardStatus?.to ?? '-')} ·
            ${htmlEscape(dashboardStatus?.total.toLocaleString() ?? '-')} total nodes ·
            exported ${htmlEscape(new Date().toLocaleString())}
          </p>
          ${dashboardStatus ? `
            <h2>Composition</h2>
            <table>
              <thead><tr><th>Entity</th><th>Count</th><th>Percentage</th></tr></thead>
              <tbody>${compositionRows}</tbody>
            </table>
          ` : ''}
          ${dashboardMetrics ? `
            <h2>Metrics</h2>
            <table>
              <thead><tr><th>Metric</th><th>Value</th><th>Total</th><th>Percentage</th><th>Status</th></tr></thead>
              <tbody>${metricRows}</tbody>
            </table>
            <h2>Rankings</h2>
            <table>
              <thead><tr><th>Ranking</th><th>Rank</th><th>Item</th><th>Value</th></tr></thead>
              <tbody>${rankingRows}</tbody>
            </table>
          ` : ''}
        </body>
      </html>
    `)
  }, [dashboardMetrics, dashboardStatus])

  return <ExportMenu enabled={Boolean(dashboardStatus || dashboardMetrics)} label="Run export" onJson={handleExportJson} onCsv={handleExportCsv} onPdf={handleExportPdf} />
}
