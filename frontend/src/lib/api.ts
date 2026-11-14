/** Backend API URL resolver and configuration. */

export const API_BASE_URL: string = (
  import.meta.env.VITE_BACKEND_URL || ''
).replace(/\/$/, '')

/** Resolves an endpoint path against the backend base URL.
 * In local dev, returns relative '/api/...' (handled by Vite proxy).
 * In production, prefixes with VITE_BACKEND_URL (e.g. 'https://...koyeb.app/api/...').
 */
export function getApiUrl(path: string): string {
  const cleanPath = path.startsWith('/') ? path : `/${path}`
  return `${API_BASE_URL}${cleanPath}`
}
