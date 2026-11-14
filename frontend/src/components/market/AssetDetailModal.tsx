import * as React from 'react'
import { useEffect, useState } from 'react'
import { Bell, Loader2, TrendingDown, TrendingUp } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { SparklineChart } from '@/components/market/SparklineChart'
import { getApiUrl } from '@/lib/api'
import { formatCurrency, formatPercent } from '@/lib/utils'
import type { SymbolAnalytics } from '@/types/market'

interface AssetDetailModalProps {
  symbol: string | null
  isOpen: boolean
  onClose: () => void
  onCreateRule?: (symbol: string) => void
}

export const AssetDetailModal: React.FC<AssetDetailModalProps> = ({
  symbol,
  isOpen,
  onClose,
  onCreateRule,
}) => {
  const [data, setData] = useState<SymbolAnalytics | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (!symbol || !isOpen) return

    const fetchDetail = async () => {
      setIsLoading(true)
      try {
        const res = await fetch(getApiUrl(`/api/v1/analytics/${symbol}`))
        if (res.ok) {
          const json: SymbolAnalytics = await res.json()
          setData(json)
        }
      } catch (err) {
        console.error('Failed to load asset analytics:', err)
      } finally {
        setIsLoading(false)
      }
    }

    fetchDetail()
  }, [symbol, isOpen])

  if (!symbol) return null
  const m = data?.metrics
  const isPositive = (m?.price_change_5m_pct ?? 0) >= 0

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-sm sm:max-w-md p-5">
        <DialogHeader>
          <div className="flex items-center justify-between pr-4">
            <DialogTitle className="text-xl font-bold flex items-center space-x-2">
              <span>{symbol.replace('USDT', '')}</span>
              <span className="text-xs text-muted-foreground font-normal">/ USDT</span>
            </DialogTitle>
            {m && (
              <Badge variant={isPositive ? 'success' : 'destructive'} className="text-xs">
                {isPositive ? <TrendingUp className="w-3 h-3 mr-1" /> : <TrendingDown className="w-3 h-3 mr-1" />}
                {formatPercent(m.price_change_5m_pct)} (5m)
              </Badge>
            )}
          </div>
          <DialogDescription className="text-xs">
            30-Minute Microstructure & Momentum Analysis
          </DialogDescription>
        </DialogHeader>

        {isLoading && !m ? (
          <div className="flex flex-col items-center justify-center p-8 space-y-2">
            <Loader2 className="w-6 h-6 animate-spin text-primary" />
            <span className="text-xs text-muted-foreground">Loading market analytics...</span>
          </div>
        ) : m ? (
          <div className="space-y-4">
            <div className="rounded-xl border border-border/60 bg-card/60 p-3 flex flex-col items-center">
              <div className="w-full flex justify-between text-xs text-muted-foreground mb-2">
                <span>Current: {formatCurrency(m.current_price)}</span>
                <span>VWAP: {formatCurrency(m.vwap)}</span>
              </div>
              <SparklineChart
                points={data?.sparkline}
                isPositive={isPositive}
                width={280}
                height={64}
                className="w-full"
              />
            </div>

            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-lg bg-secondary/40 p-2 border border-border/40">
                <div className="text-[10px] text-muted-foreground">1m Change</div>
                <div className={`text-xs font-semibold ${m.price_change_1m_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {formatPercent(m.price_change_1m_pct)}
                </div>
              </div>
              <div className="rounded-lg bg-secondary/40 p-2 border border-border/40">
                <div className="text-[10px] text-muted-foreground">15m Change</div>
                <div className={`text-xs font-semibold ${m.price_change_15m_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {formatPercent(m.price_change_15m_pct)}
                </div>
              </div>
              <div className="rounded-lg bg-secondary/40 p-2 border border-border/40">
                <div className="text-[10px] text-muted-foreground">Volatility</div>
                <div className="text-xs font-semibold text-foreground">
                  {m.volatility_pct.toFixed(2)}%
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="flex justify-between p-2 rounded-lg bg-secondary/20">
                <span className="text-muted-foreground">5m High:</span>
                <span className="font-mono font-medium">{formatCurrency(m.high_price_5m)}</span>
              </div>
              <div className="flex justify-between p-2 rounded-lg bg-secondary/20">
                <span className="text-muted-foreground">5m Low:</span>
                <span className="font-mono font-medium">{formatCurrency(m.low_price_5m)}</span>
              </div>
              <div className="flex justify-between p-2 rounded-lg bg-secondary/20">
                <span className="text-muted-foreground">Volume Spike:</span>
                <span className="font-mono font-medium">{m.volume_spike_ratio.toFixed(2)}x</span>
              </div>
              <div className="flex justify-between p-2 rounded-lg bg-secondary/20">
                <span className="text-muted-foreground">Trades (5m):</span>
                <span className="font-mono font-medium">{m.trades_count_5m}</span>
              </div>
            </div>

            <Button
              className="w-full flex items-center justify-center space-x-2"
              onClick={() => {
                onClose()
                onCreateRule?.(symbol)
              }}
            >
              <Bell className="w-4 h-4" />
              <span>Set Alert for {symbol.replace('USDT', '')}</span>
            </Button>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
