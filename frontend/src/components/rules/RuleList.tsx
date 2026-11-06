import * as React from 'react'
import { BellOff, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { RuleCard } from '@/components/rules/RuleCard'
import type { AlertRule } from '@/types/rules'

interface RuleListProps {
  rules: AlertRule[]
  isLoading: boolean
  onAddClick: () => void
  onDeleteRule: (id: number) => void
}

export const RuleList: React.FC<RuleListProps> = ({
  rules,
  isLoading,
  onAddClick,
  onDeleteRule,
}) => {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-foreground">Active Alert Rules</h2>
          <p className="text-[11px] text-muted-foreground">Automated surveillance triggers</p>
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
          <div className="font-medium text-xs text-foreground">No alerts active</div>
          <p className="text-[11px] text-muted-foreground max-w-xs">
            Create an alert rule to receive Telegram push notifications for price breakouts or volume spikes.
          </p>
          <Button size="sm" variant="outline" onClick={onAddClick} className="mt-2 text-xs">
            Create your first alert
          </Button>
        </div>
      ) : (
        <div className="space-y-2">
          {rules.map((rule) => (
            <RuleCard key={rule.id} rule={rule} onDelete={onDeleteRule} />
          ))}
        </div>
      )}
    </div>
  )
}
