/** Types for triggered alert history audit logs. */

export interface AlertHistoryItem {
  id: number
  user_id: number
  rule_id: number | null
  symbol: string
  metric_value: number
  threshold_value: number
  message: string
  triggered_at: string
}

export interface PaginatedHistory {
  items: AlertHistoryItem[]
  total: number
  page: number
  pages: number
  limit: number
}
