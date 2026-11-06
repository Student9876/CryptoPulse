import { useEffect, useState } from 'react'
import type { MarketOverview } from '@/types/market'

/** Hook that streams live market overview snapshots via Server-Sent Events (SSE). */
export function useLiveMarket() {
  const [overview, setOverview] = useState<MarketOverview | null>(null)
  const [feedStatus, setFeedStatus] = useState<'connected' | 'reconnecting' | 'offline'>('reconnecting')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let eventSource: EventSource | null = null
    let retryTimeout: ReturnType<typeof setTimeout> | null = null

    // 1. Initial snapshot fetch for instant load
    const fetchInitial = async () => {
      try {
        const res = await fetch('/api/v1/analytics/overview')
        if (res.ok) {
          const data: MarketOverview = await res.json()
          setOverview(data)
          setFeedStatus(data.feed_status as 'connected' | 'reconnecting')
        }
      } catch (err) {
        console.warn('Initial analytics fetch failed, relying on SSE:', err)
      }
    }
    fetchInitial()

    // 2. Connect to real-time SSE stream
    const connectSSE = () => {
      setFeedStatus('reconnecting')
      eventSource = new EventSource('/api/v1/stream/overview')

      eventSource.onopen = () => {
        setFeedStatus('connected')
        setError(null)
      }

      eventSource.onmessage = (event) => {
        try {
          const data: MarketOverview = JSON.parse(event.data)
          setOverview(data)
          setFeedStatus(data.feed_status as 'connected' | 'reconnecting')
        } catch (err) {
          console.error('Failed to parse SSE market snapshot:', err)
        }
      }

      eventSource.onerror = () => {
        setFeedStatus('offline')
        setError('Market stream disconnected. Reconnecting...')
        if (eventSource) {
          eventSource.close()
        }
        retryTimeout = setTimeout(connectSSE, 3000)
      }
    }

    connectSSE()

    return () => {
      if (eventSource) eventSource.close()
      if (retryTimeout) clearTimeout(retryTimeout)
    }
  }, [])

  return { overview, feedStatus, error }
}
