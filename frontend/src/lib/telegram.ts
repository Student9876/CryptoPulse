import type { TelegramWebApp } from '@/types/telegram'

/** Safely retrieves the Telegram WebApp SDK singleton if available. */
export function getTelegramWebApp(): TelegramWebApp | null {
  if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
    return window.Telegram.WebApp
  }
  return null
}

/** Initializes Telegram Mini App view (ready flag, expand viewport). */
export function initTelegramApp(): void {
  const tg = getTelegramWebApp()
  if (tg) {
    tg.ready()
    tg.expand()
  }
}

/** Provides HTTP authorization headers for backend REST API requests. */
export function getAuthHeaders(): Record<string, string> {
  const tg = getTelegramWebApp()
  if (tg?.initData) {
    return { 'X-Telegram-Init-Data': tg.initData }
  }
  // Local browser dev mode fallback
  return { 'X-Dev-Telegram-Id': '123456789' }
}

/** Triggers native Telegram device haptic vibration feedback. */
export function triggerHaptic(
  type: 'light' | 'medium' | 'heavy' | 'selection' | 'success' | 'error' = 'light'
): void {
  const tg = getTelegramWebApp()
  if (!tg?.HapticFeedback) return

  try {
    if (type === 'selection') {
      tg.HapticFeedback.selectionChanged()
    } else if (type === 'success' || type === 'error') {
      tg.HapticFeedback.notificationOccurred(type)
    } else {
      tg.HapticFeedback.impactOccurred(type)
    }
  } catch {
    // Graceful no-op if unsupported
  }
}
