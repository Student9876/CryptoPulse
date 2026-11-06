import * as React from 'react'
import { Bell, Flame, Zap } from 'lucide-react'
import type { MarketOverview } from '@/types/market'

interface MarketSummaryProps {
  overview: MarketOverview | null
  feedStatus: 'connected' | 'reconnecting' | 'offline'
}

export const MarketSummary: React.FC<MarketSummaryProps> = ({ overview, feedStatus }) => {
  const isLive = feedStatus === 'connected'

  return (
    <div className="space-y-2">
      {/* Status Bar */}
      <div className="flex items-center justify-between px-1 text-xs">
        <div className="flex items-center space-x-2">
          <span className="relative flex h-2 w-2">
            <span
              className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                isLive ? 'bg-emerald-400' : 'bg-amber-400'
              }`}
            />
            <span
              className={`relative inline-flex rounded-full h-2 w-2 ${
                isLive ? 'bg-emerald-500' : 'bg-amber-500'
              }`}
            />
          </span>
          <span className="font-medium text-muted-foreground text-[11px] capitalize">
            {feedStatus === 'connected' ? 'Live Binance Vision Feed' : feedStatus}
          </span>
        </div>

        <div className="flex items-center space-x-1 text-muted-foreground text-[11px]">
          <Bell className="w-3 h-3" />
          <span>{overview?.active_alerts_count ?? 0} active rules</span>
        </div>
      </div>

      {/* Highlights Bar */}
      {(overview?.top_mover || overview?.top_volume_spike) && (
        <div className="grid grid-cols-2 gap-2 text-xs">
          {overview?.top_mover && (
            <div className="flex items-center space-x-1.5 rounded-lg border border-border/50 bg-card/40 p-2 text-[11px]">
              <Zap className="w-3.5 h-3.5 text-primary shrink-0" />
              <div className="truncate">
                <div className="text-[10px] text-muted-foreground">Top Mover</div>
                <div className="font-semibold text-foreground truncate">{overview.top_mover}</div>
              </div>
            </div>
          )}

          {overview?.top_volume_spike && (
            <div className="flex items-center space-x-1.5 rounded-lg border border-border/50 bg-card/40 p-2 text-[11px]">
              <Flame className="w-3.5 h-3.5 text-amber-400 shrink-0" />
              <div className="truncate">
                <div className="text-[10px] text-muted-foreground">Volume Surge</div>
                <div className="font-semibold text-foreground truncate">{overview.top_volume_spike}</div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
