import * as React from 'react'
import { useState } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { ConditionType, CreateRuleInput, MetricType } from '@/types/rules'

interface CreateRuleModalProps {
  isOpen: boolean
  defaultSymbol?: string
  onClose: () => void
  onSubmit: (input: CreateRuleInput) => Promise<boolean>
}

const TRACKED_SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'DOGEUSDT', 'XRPUSDT']

export const CreateRuleModal: React.FC<CreateRuleModalProps> = ({
  isOpen,
  defaultSymbol = 'BTCUSDT',
  onClose,
  onSubmit,
}) => {
  const [symbol, setSymbol] = useState(defaultSymbol)
  const [metricType, setMetricType] = useState<MetricType>('PRICE_LEVEL')
  const [condition, setCondition] = useState<ConditionType>('GREATER_THAN')
  const [threshold, setThreshold] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const num = parseFloat(threshold)
    if (isNaN(num)) return

    setIsSubmitting(true)
    const success = await onSubmit({
      symbol,
      metric_type: metricType,
      condition,
      threshold_value: num,
    })
    setIsSubmitting(false)
    if (success) {
      setThreshold('')
      onClose()
    }
  }

  const getPlaceholder = () => {
    if (metricType === 'PRICE_LEVEL') return 'e.g. 90000'
    if (metricType === 'VOLUME_SPIKE') return 'e.g. 2.5 (ratio to baseline)'
    return 'e.g. 3.0 (percent)'
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-sm sm:max-w-md p-5">
        <DialogHeader>
          <DialogTitle className="text-lg font-bold">New Alert Rule</DialogTitle>
          <DialogDescription className="text-xs">
            Trigger notifications directly in Telegram when market conditions are met.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-3.5 mt-2">
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Asset</label>
            <Select value={symbol} onValueChange={setSymbol}>
              <SelectTrigger>
                <SelectValue placeholder="Select asset" />
              </SelectTrigger>
              <SelectContent>
                {TRACKED_SYMBOLS.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s.replace('USDT', '')} / USDT
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground">Metric</label>
              <Select value={metricType} onValueChange={(v) => setMetricType(v as MetricType)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="PRICE_LEVEL">Price Level</SelectItem>
                  <SelectItem value="PRICE_CHANGE">Price Change %</SelectItem>
                  <SelectItem value="VOLUME_SPIKE">Volume Spike</SelectItem>
                  <SelectItem value="VWAP_DEVIATION">VWAP Deviation</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground">Condition</label>
              <Select value={condition} onValueChange={(v) => setCondition(v as ConditionType)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="GREATER_THAN">Above (&gt;)</SelectItem>
                  <SelectItem value="LESS_THAN">Below (&lt;)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Threshold Target</label>
            <Input
              type="number"
              step="any"
              required
              placeholder={getPlaceholder()}
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
            />
          </div>

          <Button type="submit" disabled={isSubmitting || !threshold} className="w-full mt-2">
            <Plus className="w-4 h-4 mr-1.5" />
            <span>{isSubmitting ? 'Creating Rule...' : 'Create Alert Rule'}</span>
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}
