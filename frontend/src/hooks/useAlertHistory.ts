import { useCallback, useEffect, useState } from 'react'
import { getApiUrl } from '@/lib/api'
import { getAuthHeaders, triggerHaptic } from '@/lib/telegram'
import type { AlertHistoryItem, PaginatedHistory } from '@/types/history'

/** Hook for fetching, paginating, and managing triggered alert history logs. */
export function useAlertHistory(symbolFilter?: string) {
  const [history, setHistory] = useState<AlertHistoryItem[]>([])
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalHistory, setTotalHistory] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchHistory = useCallback(async (pageNumber = 1) => {
    setIsLoading(true)
    setError(null)
    try {
      const query = new URLSearchParams({
        page: pageNumber.toString(),
        limit: '10',
      })
      if (symbolFilter) query.set('symbol', symbolFilter)

      const res = await fetch(getApiUrl(`/api/v1/history/?${query.toString()}`), {
        headers: getAuthHeaders(),
      })
      if (!res.ok) throw new Error('Failed to load alert history')
      const data: PaginatedHistory | AlertHistoryItem[] = await res.json()
      if ('items' in data) {
        setHistory(data.items)
        setTotalPages(data.pages)
        setTotalHistory(data.total)
        setPage(data.page)
      } else {
        setHistory(data)
        setTotalHistory(data.length)
        setTotalPages(1)
        setPage(1)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error loading history')
    } finally {
      setIsLoading(false)
    }
  }, [symbolFilter])

  useEffect(() => {
    fetchHistory(1)
  }, [fetchHistory])

  const clearHistory = async (): Promise<boolean> => {
    try {
      const path = symbolFilter
        ? `/api/v1/history/?symbol=${encodeURIComponent(symbolFilter)}`
        : '/api/v1/history/'
      const res = await fetch(getApiUrl(path), {
        method: 'DELETE',
        headers: getAuthHeaders(),
      })
      if (!res.ok) throw new Error('Failed to clear history')
      setHistory([])
      setTotalHistory(0)
      setTotalPages(1)
      setPage(1)
      triggerHaptic('success')
      return true
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to clear history')
      triggerHaptic('error')
      return false
    }
  }

  return {
    history,
    page,
    totalPages,
    totalHistory,
    isLoading,
    error,
    refresh: fetchHistory,
    clearHistory,
  }
}
