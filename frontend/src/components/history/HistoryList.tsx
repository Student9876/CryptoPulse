import * as React from 'react'
import { History, RotateCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { HistoryItem } from '@/components/history/HistoryItem'
import type { AlertHistoryItem } from '@/types/history'

interface HistoryListProps {
  history: AlertHistoryItem[]
  isLoading: boolean
  onRefresh: () => void
}

export const HistoryList: React.FC<HistoryListProps> = ({
  history,
  isLoading,
  onRefresh,
}) => {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-foreground">Trigger Audit Log</h2>
          <p className="text-[11px] text-muted-foreground">Historical records of fired alerts</p>
        </div>
        <Button
          size="sm"
          variant="ghost"
          onClick={onRefresh}
          disabled={isLoading}
          className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
        >
          <RotateCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {isLoading && history.length === 0 ? (
        <div className="text-center py-8 text-xs text-muted-foreground">Loading audit log...</div>
      ) : history.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-10 text-center rounded-xl border border-dashed border-border/60 p-6 space-y-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-secondary/60 text-muted-foreground">
            <History className="w-5 h-5" />
          </div>
          <div className="font-medium text-xs text-foreground">No alerts triggered yet</div>
          <p className="text-[11px] text-muted-foreground max-w-xs">
            When market momentum or volume crosses your threshold, the event will appear here and notify your Telegram bot.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {history.map((item) => (
            <HistoryItem key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  )
}
