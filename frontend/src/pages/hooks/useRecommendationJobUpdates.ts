import { useEffect, useRef } from 'react'

export type RecommendationJobUpdate = {
  type: 'recommendation.job.updated'
  jobId: string
  status: 'queued' | 'running' | 'completed' | 'failed'
}

type RecommendationJobSocketMessage = RecommendationJobUpdate | {
  type: 'recommendation.jobs.resync'
}

// Validate the small signal before allowing it to change recommendation UI state.
function parseRecommendationJobUpdate(data: string): RecommendationJobSocketMessage | null {
  let message: unknown
  try {
    message = JSON.parse(data)
  } catch {
    return null
  }

  if (typeof message !== 'object' || message === null) return null
  if (!('type' in message)) return null
  if (message.type === 'recommendation.jobs.resync') {
    return { type: 'recommendation.jobs.resync' }
  }
  if (message.type !== 'recommendation.job.updated') return null
  if (!('jobId' in message) || typeof message.jobId !== 'string') return null
  if (!('status' in message) || typeof message.status !== 'string') return null
  if (!['queued', 'running', 'completed', 'failed'].includes(message.status)) return null

  return message as RecommendationJobUpdate
}

// Maintain one reconnecting backend WebSocket while a recommendation job is active.
export function useRecommendationJobUpdates(
  enabled: boolean,
  onUpdate: (message: RecommendationJobUpdate) => void,
  onConnected: () => void,
) {
  const onUpdateRef = useRef(onUpdate)
  const onConnectedRef = useRef(onConnected)

  useEffect(() => {
    onUpdateRef.current = onUpdate
  }, [onUpdate])

  useEffect(() => {
    onConnectedRef.current = onConnected
  }, [onConnected])

  useEffect(() => {
    if (!enabled) return

    let socket: WebSocket | undefined
    let reconnectTimer: number | undefined
    let reconnectDelayMs = 1000
    let isClosed = false

    const connect = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const token = window.localStorage.getItem('token')
      const url = `${protocol}//${window.location.host}/api/ws/recommendations?token=${encodeURIComponent(token ?? '')}`
      socket = new WebSocket(url)

      socket.onopen = () => {
        reconnectDelayMs = 1000
        onConnectedRef.current()
      }

      socket.onmessage = (event) => {
        if (typeof event.data !== 'string') return
        const message = parseRecommendationJobUpdate(event.data)
        if (message?.type === 'recommendation.jobs.resync') {
          onConnectedRef.current()
        } else if (message !== null) {
          onUpdateRef.current(message)
        }
      }

      socket.onclose = () => {
        if (isClosed) return
        reconnectTimer = window.setTimeout(connect, reconnectDelayMs)
        reconnectDelayMs = Math.min(reconnectDelayMs * 2, 30000)
      }
    }

    connect()
    return () => {
      isClosed = true
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer)
      socket?.close()
    }
  }, [enabled])
}
