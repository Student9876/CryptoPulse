import * as React from 'react'
import type { SparklinePoint } from '@/types/market'

interface SparklineChartProps {
  points?: SparklinePoint[]
  isPositive?: boolean
  width?: number
  height?: number
  className?: string
}

export const SparklineChart: React.FC<SparklineChartProps> = ({
  points = [],
  isPositive = true,
  width = 110,
  height = 32,
  className = '',
}) => {
  if (!points || points.length < 2) {
    return (
      <div className={`flex items-center justify-center text-xs text-muted-foreground ${className}`} style={{ width, height }}>
        <span className="text-[10px]">No trend</span>
      </div>
    )
  }

  const prices = points.map((p) => p.price)
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const range = max - min || 1

  const paddingY = 3
  const usableHeight = height - paddingY * 2
  const stepX = width / (points.length - 1)

  const coords = points.map((p, i) => {
    const x = i * stepX
    const y = height - paddingY - ((p.price - min) / range) * usableHeight
    return { x, y }
  })

  const pathD = coords.reduce((acc, c, i) => `${acc} ${i === 0 ? 'M' : 'L'} ${c.x.toFixed(1)},${c.y.toFixed(1)}`, '')
  const areaD = `${pathD} L ${width},${height} L 0,${height} Z`

  const strokeColor = isPositive ? '#10b981' : '#f43f5e'
  const gradientId = `spark-grad-${Math.random().toString(36).substr(2, 6)}`

  return (
    <svg width={width} height={height} className={`overflow-visible ${className}`}>
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={strokeColor} stopOpacity="0.25" />
          <stop offset="100%" stopColor={strokeColor} stopOpacity="0.0" />
        </linearGradient>
      </defs>
      <path d={areaD} fill={`url(#${gradientId})`} />
      <path d={pathD} fill="none" stroke={strokeColor} strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
