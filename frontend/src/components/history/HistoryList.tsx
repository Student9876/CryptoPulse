import * as React from 'react'
import { ChevronLeft, ChevronRight, History, RotateCw, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { HistoryItem } from '@/components/history/HistoryItem'
import type { AlertHistoryItem } from '@/types/history'

interface HistoryListProps {
  history: AlertHistoryItem[]
  isLoading: boolean
  page?: number
  totalPages?: number
  totalCount?: number
  onPageChange?: (newPage: number) => void
  onRefresh: () => void
  onClearHistory?: () => void
}

export const HistoryList: React.FC<HistoryListProps> = ({
  history,
  isLoading,
  page = 1,
  totalPages = 1,
  totalCount = 0,
  onPageChange,
  onRefresh,
  onClearHistory,
}) => {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-foreground">Trigger Audit Log</h2>
          <p className="text-[11px] text-muted-foreground">
            {totalCount > 0 ? `${totalCount} historical alerts logged` : 'Historical records of fired alerts'}
          </p>
        </div>
        <div className="flex items-center space-x-1">
          {history.length > 0 && onClearHistory && (
            <Button
              size="sm"
              variant="ghost"
              onClick={onClearHistory}
              title="Clear Audit History"
              className="h-8 px-2 text-xs text-muted-foreground hover:text-rose-400 hover:bg-rose-500/10 gap-1"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Clear</span>
            </Button>
          )}
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

          {totalPages > 1 && onPageChange && (
            <div className="flex items-center justify-between pt-2 text-xs text-muted-foreground">
              <span className="text-[11px]">
                Page {page} of {totalPages} ({totalCount} total)
              </span>
              <div className="flex items-center space-x-1">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 w-7 p-0"
                  disabled={page <= 1 || isLoading}
                  onClick={() => onPageChange(page - 1)}
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 w-7 p-0"
                  disabled={page >= totalPages || isLoading}
                  onClick={() => onPageChange(page + 1)}
                >
                  <ChevronRight className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
