import { useCallback, useEffect, useState } from 'react'
import { getApiUrl } from '@/lib/api'
import { getAuthHeaders, triggerHaptic } from '@/lib/telegram'
import type { AlertRule, CreateRuleInput } from '@/types/rules'

/** Hook providing CRUD operations for authenticated user's alert rules. */
export function useAlertRules() {
  const [rules, setRules] = useState<AlertRule[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchRules = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await fetch(getApiUrl('/api/v1/rules/'), {
        headers: getAuthHeaders(),
      })
      if (!res.ok) throw new Error('Failed to fetch alert rules')
      const data: AlertRule[] = await res.json()
      setRules(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error loading rules')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchRules()
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
      triggerHaptic('success')
      return true
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create rule')
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
    isLoading,
    error,
    refresh: fetchRules,
    createRule,
    deleteRule,
  }
}
