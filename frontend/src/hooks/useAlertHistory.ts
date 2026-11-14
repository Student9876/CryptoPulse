import { useCallback, useEffect, useState } from 'react'
import { getApiUrl } from '@/lib/api'
import { getAuthHeaders } from '@/lib/telegram'
import type { AlertHistoryItem } from '@/types/history'

/** Hook for fetching and polling triggered alert history audit logs. */
export function useAlertHistory(symbolFilter?: string) {
  const [history, setHistory] = useState<AlertHistoryItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchHistory = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const path = symbolFilter
        ? `/api/v1/history/?symbol=${encodeURIComponent(symbolFilter)}`
        : '/api/v1/history/'
      const res = await fetch(getApiUrl(path), {
        headers: getAuthHeaders(),
      })
      if (!res.ok) throw new Error('Failed to load alert history')
      const data: AlertHistoryItem[] = await res.json()
      setHistory(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error loading history')
    } finally {
      setIsLoading(false)
    }
  }, [symbolFilter])

  useEffect(() => {
    fetchHistory()
  }, [fetchHistory])

  return { history, isLoading, error, refresh: fetchHistory }
}
