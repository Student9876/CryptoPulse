import { useEffect, useState } from 'react'
import { Activity, Bell, ExternalLink, History } from 'lucide-react'
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
  const {
    rules,
    page: rulesPage,
    totalPages: rulesTotalPages,
    totalRules,
    isLoading: rulesLoading,
    createRule,
    toggleRuleActive,
    deleteRule,
    refresh: refreshRules,
  } = useAlertRules()

  const {
    history,
    page: historyPage,
    totalPages: historyTotalPages,
    totalHistory,
    isLoading: historyLoading,
    refresh: refreshHistory,
    clearHistory,
  } = useAlertHistory()

  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null)
  const [isRuleModalOpen, setIsRuleModalOpen] = useState(false)
  const [defaultRuleSymbol, setDefaultRuleSymbol] = useState('BTCUSDT')

  const isTelegram = typeof window !== 'undefined' && Boolean(window.Telegram?.WebApp?.initData)

  useEffect(() => {
    initTelegramApp()
  }, [])

  // Auto-sync when one-time rules trigger on backend and active alert count changes
  useEffect(() => {
    if (overview && overview.active_alerts_count !== undefined) {
      refreshRules(rulesPage)
    }
  }, [overview?.active_alerts_count, refreshRules, rulesPage])

  const handleTabChange = (value: string) => {
    triggerHaptic('selection')
    if (value === 'rules') {
      refreshRules(rulesPage)
    } else if (value === 'history') {
      refreshHistory(historyPage)
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

      {!isTelegram && (
        <div className="mx-3.5 mt-2 p-2.5 rounded-xl border border-cyan-500/30 bg-cyan-500/10 flex items-center justify-between text-xs text-cyan-200">
          <div className="flex items-center space-x-2">
            <span className="text-sm">🌐</span>
            <div>
              <div className="font-semibold text-cyan-100 text-[11px]">Browser Preview Mode</div>
              <div className="text-[10px] text-cyan-300/80">Open in Telegram for push alerts</div>
            </div>
          </div>
          <a
            href="https://t.me/cryptopulse10_bot"
            target="_blank"
            rel="noreferrer"
            className="flex items-center space-x-1 px-2.5 py-1 text-[11px] font-medium rounded-lg bg-cyan-500 text-slate-950 hover:bg-cyan-400 transition-colors"
          >
            <span>Open Bot</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      )}

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
              page={rulesPage}
              totalPages={rulesTotalPages}
              totalCount={totalRules}
              onPageChange={(p) => refreshRules(p)}
              onAddClick={() => setIsRuleModalOpen(true)}
              onDeleteRule={deleteRule}
              onToggleRule={toggleRuleActive}
            />
          </TabsContent>

          <TabsContent value="history" className="m-0">
            <HistoryList
              history={history}
              isLoading={historyLoading}
              page={historyPage}
              totalPages={historyTotalPages}
              totalCount={totalHistory}
              onPageChange={(p) => refreshHistory(p)}
              onRefresh={() => refreshHistory(historyPage)}
              onClearHistory={clearHistory}
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
