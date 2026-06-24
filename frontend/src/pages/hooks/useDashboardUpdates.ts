import { useEffect, useState } from 'react'

export type DashboardUpdateArea = 'composition' | 'metrics'

export type DashboardUpdate = {
  type: 'dashboard.updated'
  areas: DashboardUpdateArea[]
}

export type DashboardConnectionStatus = 'connecting' | 'connected' | 'reconnecting' | 'auth-error' | 'error'

const DASHBOARD_UPDATE_AREAS: DashboardUpdateArea[] = ['composition', 'metrics']

function isDashboardUpdateArea(value: unknown): value is DashboardUpdateArea {
  return typeof value === 'string' && DASHBOARD_UPDATE_AREAS.includes(value as DashboardUpdateArea)
}

function parseDashboardUpdate(data: string): DashboardUpdate | null {
  let message: unknown

  try {
    message = JSON.parse(data)
  } catch {
    return null
  }

  if (
    typeof message !== 'object'
    || message === null
    || !('type' in message)
    || !('areas' in message)
  ) {
    return null
  }

  const { type, areas } = message

  if (type !== 'dashboard.updated' || !Array.isArray(areas)) {
    return null
  }

  const validAreas = areas.filter(isDashboardUpdateArea)

  if (validAreas.length === 0) {
    return null
  }

  return {
    type,
    areas: validAreas,
  }
}

export function useDashboardUpdates(onUpdate: (message: DashboardUpdate) => void) {
  const [status, setStatus] = useState<DashboardConnectionStatus>('connecting')

  useEffect(() => {
    let socket: WebSocket | undefined
    let reconnectTimer: number | undefined
    let reconnectDelayMs = 1000
    let isClosed = false

    const connect = () => {
      setStatus((current) => current === 'connected' ? 'connected' : 'connecting')

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const token = window.localStorage.getItem('token')
      if (!token) {
        console.error('Dashboard WebSocket cannot connect without an auth token')
        setStatus('auth-error')
        isClosed = true
        return
      }

      const url = `${protocol}//${window.location.host}/api/ws/dashboard?token=${encodeURIComponent(token ?? '')}`

      socket = new WebSocket(url)

      socket.onopen = () => {
        reconnectDelayMs = 1000
        setStatus('connected')
      }

      socket.onmessage = (event) => {
        if (typeof event.data !== 'string') {
          return
        }

        const message = parseDashboardUpdate(event.data)

        if (message !== null) {
          onUpdate(message)
        }
      }

      socket.onerror = (event) => {
        console.error('Dashboard WebSocket error', event)

        if (!isClosed) {
          setStatus('error')
        }
      }

      socket.onclose = (event) => {
        if (isClosed) {
          return
        }

        if (event.code === 1008) {
          console.error('Dashboard WebSocket closed by policy/auth validation', {
            code: event.code,
            reason: event.reason,
          })
          setStatus('auth-error')
          isClosed = true
          return
        }

        setStatus('reconnecting')
        reconnectTimer = window.setTimeout(connect, reconnectDelayMs)
        reconnectDelayMs = Math.min(reconnectDelayMs * 2, 30000)
      }
    }

    connect()

    return () => {
      isClosed = true

      if (reconnectTimer !== undefined) {
        window.clearTimeout(reconnectTimer)
      }

      socket?.close()
    }
  }, [onUpdate])

  return status
}
