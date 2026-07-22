import {useCallback, useEffect, useMemo, useState} from 'react'
import {
  addKnownArtist,
  listKnownArtists,
  removeKnownArtist,
  type ManualArtistConnection,
} from '../../api/manualArtistConnections'

export function useManualArtistConnections(artistId: number | null, onChangeSuccess?: () => void) {
  const [connections, setConnections] = useState<ManualArtistConnection[]>([])
  const [isLoading, setIsLoading] = useState(artistId !== null)
  const [pendingArtistId, setPendingArtistId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let isCurrent = true

    if (artistId === null) {
      setConnections([])
      setIsLoading(false)
      setError(null)
      return () => { isCurrent = false }
    }

    setIsLoading(true)
    setError(null)
    listKnownArtists(artistId)
      .then((response) => {
        if (isCurrent) setConnections(response.items)
      })
      .catch((requestError) => {
        if (!isCurrent) return
        setError(requestError instanceof Error ? requestError.message : 'Failed to load known artists.')
      })
      .finally(() => {
        if (isCurrent) setIsLoading(false)
      })

    return () => { isCurrent = false }
  }, [artistId])

  const connectedArtistIds = useMemo(
    () => new Set(connections.map((connection) => connection.connectedArtistId)),
    [connections],
  )

  const add = useCallback(async (connectedArtistId: number) => {
    if (artistId === null || connectedArtistId === artistId) return

    setPendingArtistId(connectedArtistId)
    setError(null)
    try {
      const connection = await addKnownArtist(artistId, connectedArtistId)
      setConnections((current) => [
        ...current.filter((item) => item.connectedArtistId !== connection.connectedArtistId),
        connection,
      ])
      onChangeSuccess?.()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Failed to add artist.')
    } finally {
      setPendingArtistId(null)
    }
  }, [artistId, onChangeSuccess])

  const remove = useCallback(async (connectedArtistId: number) => {
    if (artistId === null) return

    setPendingArtistId(connectedArtistId)
    setError(null)
    try {
      await removeKnownArtist(artistId, connectedArtistId)
      setConnections((current) => current.filter((item) => item.connectedArtistId !== connectedArtistId))
      onChangeSuccess?.()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Failed to remove artist.')
    } finally {
      setPendingArtistId(null)
    }
  }, [artistId, onChangeSuccess])

  const toggle = useCallback((connectedArtistId: number) => {
    return connectedArtistIds.has(connectedArtistId)
      ? remove(connectedArtistId)
      : add(connectedArtistId)
  }, [add, connectedArtistIds, remove])

  return {
    connections,
    connectedArtistIds,
    isLoading,
    pendingArtistId,
    error,
    add,
    remove,
    toggle,
  }
}
