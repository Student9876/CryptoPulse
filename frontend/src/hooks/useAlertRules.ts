import { useCallback, useEffect, useState } from 'react'
import { getApiUrl } from '@/lib/api'
import { getAuthHeaders, triggerHaptic } from '@/lib/telegram'
import type { AlertRule, CreateRuleInput, PaginatedRules } from '@/types/rules'

/** Hook providing CRUD and pagination operations for user's alert rules. */
export function useAlertRules() {
  const [rules, setRules] = useState<AlertRule[]>([])
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalRules, setTotalRules] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchRules = useCallback(async (pageNumber = 1) => {
    setIsLoading(true)
    setError(null)
    try {
      // Default query filters is_active=true so triggered one-time alerts disappear
      const res = await fetch(getApiUrl(`/api/v1/rules/?page=${pageNumber}&limit=10&is_active=true`), {
        headers: getAuthHeaders(),
      })
      if (!res.ok) throw new Error('Failed to fetch alert rules')
      const data: PaginatedRules | AlertRule[] = await res.json()
      if ('items' in data) {
        setRules(data.items)
        setTotalPages(data.pages)
        setTotalRules(data.total)
        setPage(data.page)
      } else {
        setRules(data)
        setTotalRules(data.length)
        setTotalPages(1)
        setPage(1)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error loading rules')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchRules(1)
  }, [fetchRules])

  const createRule = async (input: CreateRuleInput): Promise<boolean> => {
    try {
      const res = await fetch(getApiUrl('/api/v1/rules/'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
        body: JSON.stringify(input),
      })
      if (!res.ok) throw new Error('Failed to create alert rule')
      const newRule: AlertRule = await res.json()
      setRules((prev) => [newRule, ...prev])
      setTotalRules((prev) => prev + 1)
      triggerHaptic('success')
      return true
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create rule')
      triggerHaptic('error')
      return false
    }
  }

  const toggleRuleActive = async (ruleId: number, nextActive: boolean): Promise<boolean> => {
    try {
      const res = await fetch(getApiUrl(`/api/v1/rules/${ruleId}`), {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
        body: JSON.stringify({ is_active: nextActive }),
      })
      if (!res.ok) throw new Error('Failed to update rule status')
      const updated: AlertRule = await res.json()

      // If deactivated, immediately remove from active list so one-time alerts disappear
      if (!updated.is_active) {
        setRules((prev) => prev.filter((r) => r.id !== ruleId))
        setTotalRules((prev) => Math.max(0, prev - 1))
      } else {
        setRules((prev) => prev.map((r) => (r.id === ruleId ? updated : r)))
      }
      triggerHaptic('selection')
      return true
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to toggle rule')
      triggerHaptic('error')
      return false
    }
  }

  const deleteRule = async (ruleId: number): Promise<boolean> => {
    try {
      const res = await fetch(getApiUrl(`/api/v1/rules/${ruleId}`), {
        method: 'DELETE',
        headers: getAuthHeaders(),
      })
      if (!res.ok) throw new Error('Failed to delete rule')
      setRules((prev) => prev.filter((r) => r.id !== ruleId))
      setTotalRules((prev) => Math.max(0, prev - 1))
      triggerHaptic('light')
      return true
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete rule')
      triggerHaptic('error')
      return false
    }
  }

  return {
    rules,
    page,
    totalPages,
    totalRules,
    isLoading,
    error,
    refresh: fetchRules,
    createRule,
    toggleRuleActive,
    deleteRule,
  }
}
