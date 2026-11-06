import * as React from 'react'
import { Bell, Flame, Percent, Target, Trash2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { formatCurrency } from '@/lib/utils'
import type { AlertRule } from '@/types/rules'

interface RuleCardProps {
  rule: AlertRule
  onDelete: (id: number) => void
}

export const RuleCard: React.FC<RuleCardProps> = ({ rule, onDelete }) => {
  const getMetricIcon = () => {
    switch (rule.metric_type) {
      case 'PRICE_LEVEL':
        return <Target className="w-3.5 h-3.5 text-primary" />
      case 'VOLUME_SPIKE':
        return <Flame className="w-3.5 h-3.5 text-amber-400" />
      case 'PRICE_CHANGE':
        return <Percent className="w-3.5 h-3.5 text-emerald-400" />
      case 'VWAP_DEVIATION':
        return <Bell className="w-3.5 h-3.5 text-cyan-400" />
      default:
        return <Bell className="w-3.5 h-3.5" />
    }
  }

  const formatThreshold = () => {
    const cond = rule.condition === 'GREATER_THAN' ? '>' : '<'
    if (rule.metric_type === 'PRICE_LEVEL') {
      return `${cond} ${formatCurrency(rule.threshold_value)}`
    }
    if (rule.metric_type === 'VOLUME_SPIKE') {
      return `${cond} ${rule.threshold_value}x baseline`
    }
    return `${cond} ${rule.threshold_value}%`
  }

  return (
    <Card className="p-3.5 border-border/50 bg-card/50 flex items-center justify-between">
      <div className="space-y-1">
        <div className="flex items-center space-x-2">
          <span className="font-bold text-sm tracking-wide text-foreground">
            {rule.symbol.replace('USDT', '')}
          </span>
          <Badge variant="secondary" className="text-[10px] px-1.5 py-0 gap-1">
            {getMetricIcon()}
            <span>{rule.metric_type.replace('_', ' ')}</span>
          </Badge>
        </div>

        <div className="text-sm font-semibold font-mono text-foreground">
          {formatThreshold()}
        </div>

        <div className="text-[10px] text-muted-foreground">
          Cooldown: {Math.round(rule.cooldown_seconds / 60)}m • Window: {Math.round(rule.window_seconds / 60)}m
        </div>
      </div>

      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8 text-muted-foreground hover:text-rose-400 hover:bg-rose-500/10"
        onClick={() => onDelete(rule.id)}
      >
        <Trash2 className="w-4 h-4" />
      </Button>
    </Card>
  )
}
