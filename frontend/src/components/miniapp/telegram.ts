export interface TelegramApp {
  initData: string; colorScheme: string;
  viewportHeight?: number; viewportStableHeight?: number;
  safeAreaInset?: { top: number; bottom: number }; contentSafeAreaInset?: { top: number; bottom: number };
  ready: () => void; expand: () => void; close?: () => void;
  setHeaderColor?: (color: string) => void; setBackgroundColor?: (color: string) => void;
  onEvent: (name: string, callback: () => void) => void; offEvent: (name: string, callback: () => void) => void;
  openTelegramLink?: (url: string) => void;
  enableClosingConfirmation?: () => void; disableClosingConfirmation?: () => void;
  BackButton?: { show: () => void; hide: () => void; onClick: (callback: () => void) => void; offClick: (callback: () => void) => void }
}
declare global { interface Window { Telegram?: { WebApp?: TelegramApp } } }
export function openBot(username: string) {
  const url = 'https://t.me/' + encodeURIComponent(username)
  if (window.Telegram?.WebApp?.openTelegramLink) window.Telegram.WebApp.openTelegramLink(url)
  else window.open(url, '_blank', 'noopener,noreferrer')
}
