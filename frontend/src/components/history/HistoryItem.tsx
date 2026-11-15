import * as React from 'react'
import { AlertCircle, Clock } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import type { AlertHistoryItem } from '@/types/history'

interface HistoryItemProps {
  item: AlertHistoryItem
}

export const HistoryItem: React.FC<HistoryItemProps> = ({ item }) => {
  const formatTime = (isoString: string) => {
    try {
      const date = new Date(isoString)
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    } catch {
      return isoString
    }
  }

  // Strip Telegram HTML tags and formatting dividers for clean web rendering
  const cleanMessage = item.message
    .replace(/<[^>]*>/g, '')
    .replace(/[─—]{3,}/g, '')
    .split('\n')
    .filter((line) => line.trim().length > 0)
    .join('\n')

  return (
    <Card className="p-3.5 border-border/50 bg-card/40 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Badge variant="outline" className="font-bold text-xs bg-secondary/50">
            {item.symbol.replace('USDT', '')}
          </Badge>
          <span className="text-[11px] text-muted-foreground flex items-center space-x-1">
            <Clock className="w-3 h-3 mr-0.5" />
            {formatTime(item.triggered_at)}
          </span>
        </div>

        <Badge variant="destructive" className="text-[10px] gap-1 px-1.5 py-0">
          <AlertCircle className="w-2.5 h-2.5" />
          Triggered
        </Badge>
      </div>

      <p className="text-xs text-foreground/90 leading-relaxed font-sans whitespace-pre-line">
        {cleanMessage}
      </p>

      <div className="flex items-center justify-between text-[10px] text-muted-foreground border-t border-border/30 pt-1.5 font-mono">
        <span>Actual: {item.metric_value}</span>
        <span>Target: {item.threshold_value}</span>
      </div>
    </Card>
  )
}
