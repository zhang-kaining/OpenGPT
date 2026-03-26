import { ref, watch } from 'vue'

export type ThemeMode = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'theme-mode'

function isThemeMode(v: unknown): v is ThemeMode {
  return v === 'light' || v === 'dark' || v === 'system'
}

function readThemeMode(): ThemeMode {
  const raw = localStorage.getItem(STORAGE_KEY)
  return isThemeMode(raw) ? raw : 'dark'
}

export const themeMode = ref<ThemeMode>(readThemeMode())

function apply() {
  const isDark =
    themeMode.value === 'dark' ||
    (themeMode.value === 'system' &&
      window.matchMedia('(prefers-color-scheme: dark)').matches)

  document.documentElement.classList.toggle('light', !isDark)
}

function syncToElectron(mode: ThemeMode) {
  const et = (window as any).electronTheme
  if (et?.saveMode) et.saveMode(mode)
}

export function setThemeMode(mode: ThemeMode) {
  themeMode.value = mode
  localStorage.setItem(STORAGE_KEY, mode)
  apply()
  syncToElectron(mode)
}

export function initTheme() {
  themeMode.value = readThemeMode()
  apply()
  syncToElectron(themeMode.value)

  const mq = window.matchMedia('(prefers-color-scheme: dark)')
  mq.addEventListener('change', () => {
    if (themeMode.value === 'system') apply()
  })

  watch(themeMode, (val) => {
    localStorage.setItem(STORAGE_KEY, val)
    apply()
  })
}
