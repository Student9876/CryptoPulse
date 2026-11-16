/** Types for Alert Rules and rule creation inputs. */

export type MetricType =
  | 'PRICE_LEVEL'
  | 'PRICE_CHANGE'
  | 'VOLUME_SPIKE'
  | 'VWAP_DEVIATION'

export type ConditionType = 'GREATER_THAN' | 'LESS_THAN'

export interface AlertRule {
  id: number
  user_id: number
  symbol: string
  metric_type: MetricType
  condition: ConditionType
  threshold_value: number
  window_seconds: number
  cooldown_seconds: number
  is_recurring: boolean
  is_active: boolean
  created_at: string
}

export interface CreateRuleInput {
  symbol: string
  metric_type: MetricType
  condition: ConditionType
  threshold_value: number
  window_seconds?: number
  cooldown_seconds?: number
  is_recurring?: boolean
}

export interface PaginatedRules {
  items: AlertRule[]
  total: number
  page: number
  pages: number
  limit: number
}
