import { useEffect, useState } from 'react'
import { Activity, Bell, History } from 'lucide-react'
import { Header } from '@/components/layout/Header'
import { HistoryList } from '@/components/history/HistoryList'
import { AssetDetailModal } from '@/components/market/AssetDetailModal'
import { MarketSummary } from '@/components/market/MarketSummary'
import { TickerCard } from '@/components/market/TickerCard'
import { CreateRuleModal } from '@/components/rules/CreateRuleModal'
import { RuleList } from '@/components/rules/RuleList'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAlertHistory } from '@/hooks/useAlertHistory'
import { useAlertRules } from '@/hooks/useAlertRules'
import { useLiveMarket } from '@/hooks/useLiveMarket'
import { initTelegramApp, triggerHaptic } from '@/lib/telegram'

export default function App() {
  const { overview, feedStatus } = useLiveMarket()
  const { rules, isLoading: rulesLoading, createRule, deleteRule, refresh: refreshRules } = useAlertRules()
  const { history, isLoading: historyLoading, refresh: refreshHistory } = useAlertHistory()

  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null)
  const [isRuleModalOpen, setIsRuleModalOpen] = useState(false)
  const [defaultRuleSymbol, setDefaultRuleSymbol] = useState('BTCUSDT')

  useEffect(() => {
    initTelegramApp()
  }, [])

  const handleTabChange = (value: string) => {
    triggerHaptic('selection')
    if (value === 'rules') {
      refreshRules()
    } else if (value === 'history') {
      refreshHistory()
    }
  }

  const handleCreateRuleForAsset = (symbol: string) => {
    setDefaultRuleSymbol(symbol)
    setIsRuleModalOpen(true)
  }

  const symbolsList = overview?.symbols ? Object.values(overview.symbols) : []

  return (
    <div className="min-h-screen bg-background text-foreground pb-8 flex flex-col max-w-md mx-auto">
      <Header />

      <main className="flex-1 p-3.5 space-y-3.5">
        <Tabs defaultValue="market" onValueChange={handleTabChange} className="w-full">
          <TabsList className="grid w-full grid-cols-3 mb-3">
            <TabsTrigger value="market" className="gap-1.5 text-xs">
              <Activity className="w-3.5 h-3.5" />
              <span>Market</span>
            </TabsTrigger>
            <TabsTrigger value="rules" className="gap-1.5 text-xs">
              <Bell className="w-3.5 h-3.5" />
              <span>Alerts</span>
            </TabsTrigger>
            <TabsTrigger value="history" className="gap-1.5 text-xs">
              <History className="w-3.5 h-3.5" />
              <span>History</span>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="market" className="space-y-3 m-0">
            <MarketSummary overview={overview} feedStatus={feedStatus} />
            <div className="space-y-2">
              {symbolsList.length === 0 ? (
                <div className="text-center py-12 text-xs text-muted-foreground">
                  Streaming Binance live quotes...
                </div>
              ) : (
                symbolsList.map((m) => (
                  <TickerCard key={m.symbol} metrics={m} onSelect={setSelectedSymbol} />
                ))
              )}
            </div>
          </TabsContent>

          <TabsContent value="rules" className="m-0">
            <RuleList
              rules={rules}
              isLoading={rulesLoading}
              onAddClick={() => setIsRuleModalOpen(true)}
              onDeleteRule={deleteRule}
            />
          </TabsContent>

          <TabsContent value="history" className="m-0">
            <HistoryList
              history={history}
              isLoading={historyLoading}
              onRefresh={refreshHistory}
            />
          </TabsContent>
        </Tabs>
      </main>

      <AssetDetailModal
        symbol={selectedSymbol}
        isOpen={Boolean(selectedSymbol)}
        onClose={() => setSelectedSymbol(null)}
        onCreateRule={handleCreateRuleForAsset}
      />

      <CreateRuleModal
        isOpen={isRuleModalOpen}
        defaultSymbol={defaultRuleSymbol}
        onClose={() => setIsRuleModalOpen(false)}
        onSubmit={createRule}
      />
    </div>
  )
}
