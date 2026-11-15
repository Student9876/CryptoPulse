import * as React from 'react'
import { useEffect, useRef, useState } from 'react'
import { Flame, TrendingDown, TrendingUp } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { formatCurrency, formatPercent } from '@/lib/utils'
import type { SymbolMetrics } from '@/types/market'

interface TickerCardProps {
  metrics: SymbolMetrics
  onSelect?: (symbol: string) => void
}

export const TickerCard: React.FC<TickerCardProps> = ({ metrics, onSelect }) => {
  const [flash, setFlash] = useState<'up' | 'down' | null>(null)
  const prevPriceRef = useRef<number>(metrics.current_price)

  useEffect(() => {
    if (metrics.current_price > prevPriceRef.current) {
      setFlash('up')
    } else if (metrics.current_price < prevPriceRef.current) {
      setFlash('down')
    }
    prevPriceRef.current = metrics.current_price

    const timer = setTimeout(() => setFlash(null), 600)
    return () => clearTimeout(timer)
  }, [metrics.current_price])

  const isPositive = metrics.price_change_5m_pct >= 0
  const isSpiking = metrics.volume_spike_ratio >= 1.5

  const vwapValue = metrics.vwap_5m ?? metrics.vwap ?? metrics.current_price
  const takerBuyPct =
    metrics.taker_buy_ratio_pct ??
    (metrics.taker_buy_ratio !== undefined ? metrics.taker_buy_ratio * 100 : 50)

  const flashClass =
    flash === 'up'
      ? 'bg-emerald-500/10 border-emerald-500/40'
      : flash === 'down'
      ? 'bg-rose-500/10 border-rose-500/40'
      : 'hover:border-border'

  return (
    <Card
      onClick={() => onSelect?.(metrics.symbol)}
      className={`cursor-pointer p-3.5 transition-all duration-300 ${flashClass}`}
    >
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-1.5">
            <span className="font-bold text-sm tracking-wide text-foreground">
              {metrics.symbol.replace('USDT', '')}
            </span>
            <span className="text-[10px] text-muted-foreground">/USDT</span>
            {isSpiking && (
              <Badge variant="warning" className="px-1 py-0 text-[9px] gap-0.5">
                <Flame className="w-2.5 h-2.5 text-amber-400" />
                {metrics.volume_spike_ratio.toFixed(1)}x
              </Badge>
            )}
          </div>
          <div className="text-lg font-semibold tracking-tight text-foreground mt-0.5">
            {formatCurrency(metrics.current_price)}
          </div>
        </div>

        <div className="flex flex-col items-end space-y-1">
          <Badge
            variant={isPositive ? 'success' : 'destructive'}
            className="flex items-center space-x-0.5 text-xs font-semibold px-2"
          >
            {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
            <span>{formatPercent(metrics.price_change_5m_pct)}</span>
          </Badge>
          <span className="text-[10px] text-muted-foreground font-mono">
            VWAP {formatCurrency(vwapValue)}
          </span>
        </div>
      </div>

      <div className="mt-2.5 pt-2 border-t border-border/40 flex items-center justify-between text-[11px] text-muted-foreground">
        <div className="flex items-center space-x-2">
          <span>Taker Buy:</span>
          <div className="w-16 h-1.5 rounded-full bg-rose-500/30 overflow-hidden">
            <div
              className="h-full bg-emerald-500 transition-all duration-300"
              style={{ width: `${Math.min(Math.max(takerBuyPct, 0), 100)}%` }}
            />
          </div>
          <span className="font-mono text-[10px]">{takerBuyPct.toFixed(0)}%</span>
        </div>

        <span className="text-[10px]">5m Vol: {metrics.volume_5m.toFixed(1)}</span>
      </div>
    </Card>
  )
}
