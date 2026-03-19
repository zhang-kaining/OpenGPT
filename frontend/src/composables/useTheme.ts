import { ref, watch } from 'vue'

export type ThemeMode = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'theme-mode'

export const themeMode = ref<ThemeMode>(
  (localStorage.getItem(STORAGE_KEY) as ThemeMode) || 'dark'
)

function apply() {
  const isDark =
    themeMode.value === 'dark' ||
    (themeMode.value === 'system' &&
      window.matchMedia('(prefers-color-scheme: dark)').matches)

  document.documentElement.classList.toggle('light', !isDark)
}

export function initTheme() {
  apply()

  const mq = window.matchMedia('(prefers-color-scheme: dark)')
  mq.addEventListener('change', () => {
    if (themeMode.value === 'system') apply()
  })

  watch(themeMode, (val) => {
    localStorage.setItem(STORAGE_KEY, val)
    apply()
  })
}
