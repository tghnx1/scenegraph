import { AdminUsersPage } from "./AdminUsersPage"
import { getActivityLog, type ActivityLogItem, exportActivityLog } from "../api/auth"
import {useCallback, useEffect, useState} from 'react'
import {fetchDashboardStatus} from '../api/dashboardComposition'
import {fetchDashboardMetrics} from '../api/dashboardMetrics'
import {useApi} from '../api/useApi'
import type {DashboardEntity} from '../types/dashboardComposition'
import {DashboardExportMenu} from './components/ExportDashboard'
import {DashboardImportButton} from './components/ImportDashboard'
import {DashboardMetricPanels} from './components/DashboardMetric'
import {DashboardStatistics} from './components/DashboardComposition'
import {useDashboardUpdates, type DashboardUpdate} from './hooks/useDashboardUpdates'

export function DashboardPage() {
  const [selectedEntities, setSelectedEntities] = useState<DashboardEntity[]>([
    'events',
    'artists',
    'promoters',
    'venues',
  ])
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [activityRows, setActivityRows] = useState<ActivityLogItem[]>([])
  const include = selectedEntities.join(',')
  const {
    data: dashboardStatus,
    isLoading,
    error,
    refetch: refetchComposition,
  } = useApi(
    () => fetchDashboardStatus({entities: selectedEntities, dateFrom, dateTo}),
    [include, dateFrom, dateTo]
  )
  const {
    data: dashboardMetrics,
    isLoading: areMetricsLoading,
    error: metricsError,
    refetch: refetchMetrics,
  } = useApi(fetchDashboardMetrics, [])

  const loadActivity = useCallback(async () => {
    try {
      const response = await getActivityLog()
      setActivityRows(response.activity)
    } catch (error) {
      console.error(error)
    }
  }, [])

  const handleDashboardUpdate = useCallback(
    ({areas}: DashboardUpdate) => {
      if (areas.includes('composition')) {
        void refetchComposition()
      }

      if (areas.includes('metrics')) {
        void refetchMetrics()
      }
    },
    [refetchComposition, refetchMetrics],
  )

  const dashboardConnectionStatus = useDashboardUpdates(handleDashboardUpdate)
  const dashboardConnectionMessage = (() => {
    switch (dashboardConnectionStatus) {
      case 'connecting':
        return 'Connecting live dashboard updates...'
      case 'reconnecting':
      case 'error':
        return 'Live dashboard updates are reconnecting.'
      case 'auth-error':
        return 'Live dashboard updates stopped because your session could not be validated.'
      case 'connected':
      default:
        return ''
    }
  })()

  const toggleEntity = (entity: DashboardEntity) => {
    setSelectedEntities((current) => current.includes(entity)
      ? current.filter((item) => item !== entity)
      : [...current, entity]
    )
  }

  useEffect(() => {
    void loadActivity()
  }, [])

  return (
    <div className="mx-auto min-h-full w-full max-w-[1480px] p-4">
      <div className="mb-4 flex flex-wrap items-center justify-end gap-2" aria-label="Dashboard actions">
        <DashboardImportButton />
        <DashboardExportMenu
          dashboardStatus={dashboardStatus}
          dashboardMetrics={dashboardMetrics}
          selectedEntities={selectedEntities}
          dateFrom={dateFrom}
          dateTo={dateTo}
        />
      </div>

      {error && <p className="mt-5 text-[var(--event)]">Failed to load dashboard status.</p>}
      {dashboardConnectionMessage && (
        <p className="mt-3 text-sm text-[color-mix(in_srgb,var(--text)_70%,transparent)]">
          {dashboardConnectionMessage}
        </p>
      )}

      <section className="grid min-w-0 gap-5" aria-label="Admin dashboard sections">
        <DashboardStatistics
          dashboardStatus={dashboardStatus}
          isLoading={isLoading}
          hasError={Boolean(error)}
          selectedEntities={selectedEntities}
          onToggleEntity={toggleEntity}
          dateFrom={dateFrom}
          dateTo={dateTo}
          onDateRangeChange={(nextDateFrom, nextDateTo) => {
            setDateFrom(nextDateFrom)
            setDateTo(nextDateTo)
          }}
        />
        <DashboardMetricPanels
          dashboardMetrics={dashboardMetrics}
          isLoading={areMetricsLoading}
          hasError={Boolean(metricsError)}
        />

        <div className="grid min-w-0 gap-6 lg:grid-cols-2">
          <AdminUsersPage compact onActivityChanged={loadActivity} />

          <section className="min-w-0">
            <div
              className="mb-3 flex flex-wrap items-center justify-between gap-2"
            >
              <span>Login, logout, and registration activity</span>
              <button 
                type="button"
                onClick={exportActivityLog}
                style={{
                  padding: '8px 12px',
                  borderRadius: 8,
                  border: '1px solid color-mix(in srgb, var(--text) 20%, transparent)',
                  background: 'color-mix(in srgb, var(--background) 88%, var(--text) 8%)',
                }}                
              >
                Export activity log
              </button>
            </div>

            <div
              className="dashboard-scroll-list"
              style={{
                maxHeight: 490,
                overflowY: 'auto',
                display: 'grid',
                gap: 6,
                fontFamily: 'monospace',
                fontSize: 13,
              }}
            >
              {activityRows.map((row) => (
                <div
                  key={row.id}
                  className="grid grid-cols-1 gap-3 border-b border-[color-mix(in_srgb,var(--text)_12%,transparent)] py-1.5 min-[701px]:grid-cols-[170px_120px_minmax(0,1fr)]"
                >
                  <span className="min-w-0 break-words">{new Date(row.created_at).toLocaleString()}</span>
                  <strong className="min-w-0 break-words">{row.event_type}</strong>
                  <span className="min-w-0 break-words">
                    {row.username ?? 'unknown'} → {row.target ?? '-'}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </div>
      </section>
    </div>
  )
}
