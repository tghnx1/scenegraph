const BASE = '/api' //vite proxy rule, cn be changed if the prefix changes. all api calls are relative to /api

async function request<T>( //typescript generics, request<GraphData> returns Promise<GraphData>
  path: string, 
  options: RequestInit = {}
): Promise<T> {

  const token = localStorage.getItem('token') //if given, reads the Json Web Token saved at login

  const res = await fetch(`${BASE}${path}`, { //fetch() is the browser's builtin http function, actual network call
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })

  if (res.status === 401) { //redirect to login
    localStorage.removeItem('token')
    window.location.href = '/login'
  }

  if (!res.ok) { //anything other than  200–299 throw an error that useApi's catch block will catch and put in the error state
    throw new Error(`${res.status} ${res.statusText}`)
  }

  return res.json() as Promise<T> //parses the response body as json and returns it as type t
}

export const api = { //exported api object --> public interface. everything else call api.get<GraphData>('/graph') or api.post('/auth/login', body), never request() directly.
  get:  <T>(path: string) =>
    request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
}