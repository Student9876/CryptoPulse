/** Backend API URL resolver and configuration. */

export const API_BASE_URL: string = (
  import.meta.env.BACKEND_URL ||
  import.meta.env.VITE_BACKEND_URL ||
  ''
).replace(/\/$/, '')

/** Resolves an endpoint path against the backend base URL.
 * In local dev, returns relative '/api/...' (handled by Vite proxy).
 * In production, prefixes with BACKEND_URL (e.g. 'https://...onrender.com/api/...').
 */
export function getApiUrl(path: string): string {
  const cleanPath = path.startsWith('/') ? path : `/${path}`
  return `${API_BASE_URL}${cleanPath}`
}
