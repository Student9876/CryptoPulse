import * as React from 'react'
import { Radio } from 'lucide-react'
import { getTelegramWebApp } from '@/lib/telegram'

export const Header: React.FC = () => {
  const tg = getTelegramWebApp()
  const user = tg?.initDataUnsafe?.user

  return (
    <header className="sticky top-0 z-40 flex items-center justify-between border-b border-border/40 bg-background/80 px-4 py-3 backdrop-blur-md">
      <div className="flex items-center space-x-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/20 text-primary">
          <Radio className="h-4 w-4 animate-pulse" />
        </div>
        <div>
          <h1 className="text-sm font-bold tracking-tight text-foreground">CryptoPulse</h1>
          <p className="text-[10px] text-muted-foreground leading-none">Real-Time Intelligence</p>
        </div>
      </div>

      <div className="flex items-center space-x-2">
        <div className="rounded-full bg-secondary/80 px-2.5 py-1 text-[11px] font-medium text-secondary-foreground border border-border/40">
          {user?.first_name ? `@${user.first_name}` : 'Live Client'}
        </div>
      </div>
    </header>
  )
}
