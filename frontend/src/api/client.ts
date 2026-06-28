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

  if (res.status === 401 || res.status === 403) { //redirect to login (401 unauthorized, 403 forbidden)
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    localStorage.removeItem('username')
    localStorage.removeItem('user_id')
    localStorage.removeItem('artist_id')
    sessionStorage.setItem('auth_message', 'Your account is no longer active.')
    window.location.href = '/login'
  }

  if (!res.ok) { //anything other than  200–299 throw an error that useApi's catch block will catch and put in the error state
    const errorData = await res.json().catch(() => null)

    throw new Error(
      errorData?.detail ??
      `Request failed (${res.status})`
  )
}

  return res.json() as Promise<T> //parses the response body as json and returns it as type t
}

//options necessary to fit the headers for the pending users
export const api = { //exported api object --> public interface. everything else call api.get<GraphData>('/graph') or api.post('/auth/login', body), never request() directly.
  get:  <T>(path: string, options: RequestInit = {}) =>
    request<T>(path, options),
  post: <T>(path: string, body: unknown, options: RequestInit = {}) =>
    request<T>(path, { ...options, method: 'POST', body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path: string) =>
    request<T>(path, { method: 'DELETE' }),
}
