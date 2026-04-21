import { 
  useState, //stores data/loading/error
  useEffect, //runs the fetch when something changes
  useCallback //memoizes the load function so it doesn't re-create on every render
} from 'react' //react hooks

interface ApiState<T> { //T is filled in by the caller, could be GraphData, Artist, etc.
  data:      T | null //the result
  isLoading: boolean //whether it's otw
  error:     string | null
}

//deps works like useEffect's dependency array. the hook re-fetches whenever a dep value changes
export function useApi<T>( //custom react hook, by convention hooks start with use, <T> generic is inferred automatically from what fetcher returns
  fetcher: () => Promise<T>, //fetcher parameter, function that returns a Promise, doesn't care what the function does. it just calls it and handles loading/error. we pass () => fetchGraph({...})
  deps: unknown[] = [] //deps/dependency parameter
) {
  const [state, setState] = 
    useState<ApiState<T>>({ //initial state. isLoading: true immediately, so the component shows "Loading..." before the first fetch even starts. data: null until the response arrives.
      data: null, 
      isLoading: true, 
      error: null,
  })

  const load = useCallback(async () => { //useCallback memoizes load function. without this, load would be a new function reference on every render, causing useEffect to run infinitely
    setState(s => ({ ...s, isLoading: true, error: null }))
    try {
      const data = await fetcher() //actual call to API function. if resolves, updates state with the data
      setState({ data, isLoading: false, error: null })
    } catch (err) {
      setState({
        data: null,
        isLoading: false,
        error: err instanceof Error ? err.message : 'Request failed',
      })
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps) //deps passed to useCallback. when any value in deps changes, useCallback creates a new load function, which triggers useEffect, which re-fetches(re-fetch mechanism)

  useEffect(() => { load() }, [load]) //runs load() when load changes (i.e. when deps change), also runs on mount. this is what fires the initial fetch

  return { ...state, refetch: load }
}