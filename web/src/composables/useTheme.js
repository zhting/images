import { ref, watch } from 'vue'

/**
 * Theme: dark (default) / light / system. Photos read better on dark,
 * but text-heavy pages (settings, documents) are easier on light —
 * following the OS is the safest default for people who care.
 */
const KEY = 'dp_theme'
const stored = (() => {
  try { return localStorage.getItem(KEY) } catch (e) { return null }
})()

export const theme = ref(stored || 'dark')   // 'dark' | 'light' | 'system'

const media = typeof window !== 'undefined' && window.matchMedia
  ? window.matchMedia('(prefers-color-scheme: light)')
  : null

const resolve = (t) => (t === 'system' ? (media && media.matches ? 'light' : 'dark') : t)

const apply = () => {
  const cls = document.documentElement.classList
  const effective = resolve(theme.value)
  cls.toggle('theme-light', effective === 'light')
  cls.toggle('theme-dark', effective === 'dark')
}

watch(theme, (t) => {
  try { localStorage.setItem(KEY, t) } catch (e) { /* private mode */ }
  apply()
}, { immediate: true })

media?.addEventListener?.('change', () => { if (theme.value === 'system') apply() })

export const setTheme = (t) => { theme.value = t }
