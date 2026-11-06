/** Types for market statistics, rolling window metrics, and sparklines. */

export interface SymbolMetrics {
  symbol: string
  current_price: number
  vwap: number
  price_change_1m_pct: number
  price_change_5m_pct: number
  price_change_15m_pct: number
  volume_5m: number
  volume_spike_ratio: number
  taker_buy_ratio: number
  volatility_pct: number
  trades_count_5m: number
  high_price_5m: number
  low_price_5m: number
  last_trade_time_ms: number
}

export interface SparklinePoint {
  timestamp_ms: number
  price: number
}

export interface SymbolAnalytics {
  metrics: SymbolMetrics
  sparkline: SparklinePoint[]
}

export interface MarketOverview {
  server_time: string
  feed_status: 'connected' | 'reconnecting' | 'degraded' | string
  top_mover: string | null
  top_volume_spike: string | null
  symbols: Record<string, SymbolMetrics>
  active_alerts_count: number
}
