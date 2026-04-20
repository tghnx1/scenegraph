import { useState, useEffect, useCallback } from 'react'

interface ApiState<T> {
  data:      T | null
  isLoading: boolean
  error:     string | null
}

//deps works like useEffect's dependency array:
//the hook re-fetches whenever a dep value changes
export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = []
) {
  const [state, setState] = useState<ApiState<T>>({
    data: null, isLoading: true, error: null,
  })

  const load = useCallback(async () => {
    setState(s => ({ ...s, isLoading: true, error: null }))
    try {
      const data = await fetcher()
      setState({ data, isLoading: false, error: null })
    } catch (err) {
      setState({
        data: null,
        isLoading: false,
        error: err instanceof Error ? err.message : 'Request failed',
      })
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => { load() }, [load])

  return { ...state, refetch: load }
}