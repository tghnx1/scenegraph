import {useCallback, useState} from 'react'
import type {DashboardEntity, DashboardStatus} from '../../types/dashboardComposition'

interface DashboardExportMenuProps {
  dashboardStatus: DashboardStatus | null
  selectedEntities: DashboardEntity[]
  dateFrom: string
  dateTo: string
}

function downloadTextFile(filename: string, content: string, type: string) {
  const blob = new Blob([content], {type})
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

function csvCell(value: unknown) {
  return `"${String(value ?? '').replaceAll('"', '""')}"`
}

function htmlEscape(value: unknown) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

export function DashboardExportMenu({
  dashboardStatus,
  selectedEntities,
  dateFrom,
  dateTo,
}: DashboardExportMenuProps) {
  const [isExportMenuOpen, setIsExportMenuOpen] = useState(false)

  const handleExportJson = useCallback(() => {
    if (!dashboardStatus) return
    setIsExportMenuOpen(false)
    downloadTextFile(
      'dashboard-composition.json',
      JSON.stringify({
        exportedAt: new Date().toISOString(),
        filters: {include: selectedEntities, dateFrom: dateFrom || null, dateTo: dateTo || null},
        data: dashboardStatus,
      }, null, 2),
      'application/json;charset=utf-8',
    )
  }, [dashboardStatus, dateFrom, dateTo, selectedEntities])

  const handleExportCsv = useCallback(() => {
    if (!dashboardStatus) return
    setIsExportMenuOpen(false)
    const rows = dashboardStatus.items.map((item) => [
      item.id,
      item.label,
      item.value,
      item.percentage,
      dashboardStatus.from,
      dashboardStatus.to,
    ])
    const csv = [
      ['entity', 'label', 'value', 'percentage', 'from', 'to'],
      ...rows,
    ].map((row) => row.map(csvCell).join(',')).join('\n')
    downloadTextFile('dashboard-composition.csv', csv, 'text/csv;charset=utf-8')
  }, [dashboardStatus])

  const handleExportPdf = useCallback(() => {
    if (!dashboardStatus) return
    setIsExportMenuOpen(false)
    const popup = window.open('', '_blank')
    if (!popup) return
    const rows = dashboardStatus.items.map((item) => `
      <tr>
        <td>${htmlEscape(item.label)}</td>
        <td>${htmlEscape(item.value.toLocaleString())}</td>
        <td>${htmlEscape(item.percentage.toFixed(2))}%</td>
      </tr>
    `).join('')
    popup.document.write(`
      <!doctype html>
      <html>
        <head>
          <title>Dashboard Composition</title>
          <style>
            body { color: #1f2724; font-family: Arial, sans-serif; margin: 32px; }
            h1 { margin-bottom: 8px; }
            .meta { color: #60706a; margin-bottom: 24px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border-bottom: 1px solid #d8dfdc; padding: 10px; text-align: left; }
            th { background: #f2f5f3; }
            @page { margin: 18mm; }
          </style>
        </head>
        <body>
          <h1>Dashboard Composition</h1>
          <p class="meta">
            ${htmlEscape(dashboardStatus.from)} to ${htmlEscape(dashboardStatus.to)} ·
            ${htmlEscape(dashboardStatus.total.toLocaleString())} total nodes ·
            exported ${htmlEscape(new Date().toLocaleString())}
          </p>
          <table>
            <thead><tr><th>Entity</th><th>Count</th><th>Percentage</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </body>
      </html>
    `)
    popup.document.close()
    popup.focus()
    window.setTimeout(() => popup.print(), 250)
  }, [dashboardStatus])

  return (
    <div className="export-menu">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={isExportMenuOpen}
        disabled={!dashboardStatus}
        onClick={() => setIsExportMenuOpen((isOpen) => !isOpen)}
      >
        Export
      </button>
      {isExportMenuOpen && dashboardStatus && (
        <div className="export-menu-list" role="menu" aria-label="Export dashboard composition">
          <button type="button" role="menuitem" onClick={handleExportJson}>JSON</button>
          <button type="button" role="menuitem" onClick={handleExportCsv}>CSV</button>
          <button type="button" role="menuitem" onClick={handleExportPdf}>PDF</button>
        </div>
      )}
    </div>
  )
}
