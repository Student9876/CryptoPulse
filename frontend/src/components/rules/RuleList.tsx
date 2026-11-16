import * as React from 'react'
import { BellOff, ChevronLeft, ChevronRight, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { RuleCard } from '@/components/rules/RuleCard'
import type { AlertRule } from '@/types/rules'

interface RuleListProps {
  rules: AlertRule[]
  isLoading: boolean
  page?: number
  totalPages?: number
  totalCount?: number
  onPageChange?: (newPage: number) => void
  onAddClick: () => void
  onDeleteRule: (id: number) => void
  onToggleRule?: (id: number, nextActive: boolean) => void
}

export const RuleList: React.FC<RuleListProps> = ({
  rules,
  isLoading,
  page = 1,
  totalPages = 1,
  totalCount = 0,
  onPageChange,
  onAddClick,
  onDeleteRule,
  onToggleRule,
}) => {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-foreground">Active Alert Rules</h2>
          <p className="text-[11px] text-muted-foreground">
            {totalCount > 0 ? `${totalCount} automated triggers configured` : 'Automated surveillance triggers'}
          </p>
        </div>
        <Button size="sm" onClick={onAddClick} className="h-8 text-xs gap-1">
          <Plus className="w-3.5 h-3.5" />
          <span>New Alert</span>
        </Button>
      </div>

      {isLoading && rules.length === 0 ? (
        <div className="text-center py-8 text-xs text-muted-foreground">Loading rules...</div>
      ) : rules.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-10 text-center rounded-xl border border-dashed border-border/60 p-6 space-y-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-secondary/60 text-muted-foreground">
            <BellOff className="w-5 h-5" />
          </div>
          <div className="font-medium text-xs text-foreground">No active alerts</div>
          <p className="text-[11px] text-muted-foreground max-w-xs">
            Triggered one-time alerts auto-deactivate after firing. Create a new alert rule to monitor price levels or volume spikes.
          </p>
          <Button size="sm" variant="outline" onClick={onAddClick} className="mt-2 text-xs">
            Create your first alert
          </Button>
        </div>
      ) : (
        <div className="space-y-2">
          {rules.map((rule) => (
            <RuleCard
              key={rule.id}
              rule={rule}
              onDelete={onDeleteRule}
              onToggleActive={onToggleRule}
            />
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
