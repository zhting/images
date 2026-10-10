<template>
  <div class="frame fixed inset-0 z-[5000] bg-black text-white select-none overflow-hidden"
       :class="{ 'cursor-none': !chrome }"
       @mousemove="poke" @click="onTap" @touchstart.passive="onTouchStart" @touchend="onTouchEnd">

    <!-- Two layers cross-fade -->
    <div v-for="(l, i) in layers" :key="i" class="absolute inset-0 transition-opacity ease-in-out"
         :style="{ opacity: active === i ? 1 : 0, transitionDuration: FADE_MS + 'ms' }" aria-hidden="true">
      <template v-if="l.src">
        <img v-if="settings.fit === 'contain'" :src="l.src" class="absolute inset-0 w-full h-full object-cover scale-110 blur-3xl brightness-50" alt="" />
        <img :key="l.src" :src="l.src" class="absolute inset-0 w-full h-full"
             :class="[settings.fit === 'contain' ? 'object-contain' : 'object-cover', settings.kenBurns ? 'kenburns' : '']"
             :style="{ '--kb-origin': l.origin, '--kb-ms': (settings.interval * 1000 + FADE_MS * 2) + 'ms' }"
             :alt="l.item?.place || ''" />
      </template>
    </div>

    <!-- Clock + caption -->
    <div class="absolute inset-x-0 bottom-0 p-6 sm:p-10 flex items-end justify-between gap-6 pointer-events-none bg-gradient-to-t from-black/50 via-black/10 to-transparent">
      <div v-if="settings.clock" class="drop-shadow-lg">
        <div class="text-6xl sm:text-8xl font-extralight tabular-nums leading-none tracking-tight">{{ clock.time }}</div>
        <div class="mt-2 text-lg sm:text-xl text-white/80">{{ clock.date }}</div>
      </div>
      <div v-else></div>
      <div v-if="settings.info && current" class="text-right drop-shadow-lg max-w-[50%]">
        <div v-if="current.place" class="text-lg sm:text-2xl font-light truncate">{{ current.place }}</div>
        <div class="text-sm sm:text-base text-white/70">{{ takenOn(current.captured_time) }}</div>
      </div>
    </div>

    <!-- Empty / error -->
    <div v-if="state !== 'playing'" class="absolute inset-0 flex flex-col items-center justify-center text-center p-6">
      <div v-if="state === 'loading'" class="text-white/60 animate-pulse">正在准备照片…</div>
      <template v-else>
        <p class="text-white/80 mb-4">{{ state === 'empty' ? '这个来源里没有可放映的照片' : '照片加载失败' }}</p>
        <div class="flex gap-3">
          <button class="px-4 py-2 rounded-full bg-white/15 hover:bg-white/25" @click.stop="openPanel = true; poke()">换个来源</button>
          <button class="px-4 py-2 rounded-full bg-white/15 hover:bg-white/25" @click.stop="exit">退出</button>
        </div>
      </template>
    </div>

    <!-- Controls -->
    <transition name="fade">
      <div v-show="chrome" class="absolute inset-x-0 top-0 p-3 sm:p-4 flex items-center gap-2 bg-gradient-to-b from-black/60 to-transparent" @click.stop>
        <button class="ctl" @click="exit" aria-label="退出放映"><X :size="20" /></button>
        <div class="text-sm text-white/80 truncate mr-auto">
          {{ label }}<span v-if="items.length" class="text-white/50"> · {{ index + 1 }}/{{ items.length }}</span>
        </div>
        <button class="ctl" @click="step(-1)" aria-label="上一张"><SkipBack :size="18" /></button>
        <button class="ctl" @click="togglePause" :aria-label="paused ? '继续' : '暂停'">
          <Play v-if="paused" :size="18" fill="currentColor" /><Pause v-else :size="18" fill="currentColor" />
        </button>
        <button class="ctl" @click="step(1)" aria-label="下一张"><SkipForward :size="18" /></button>
        <button class="ctl" @click="openPanel = !openPanel" aria-label="放映设置" :aria-expanded="String(openPanel)"><Settings2 :size="18" /></button>
        <button v-if="canFullscreen" class="ctl" @click="toggleFullscreen" :aria-label="isFullscreen ? '退出全屏' : '全屏'">
          <Minimize v-if="isFullscreen" :size="18" /><Maximize v-else :size="18" />
        </button>
      </div>
    </transition>

    <!-- Settings panel -->
    <div v-if="openPanel" class="absolute top-16 right-3 sm:right-4 w-[min(22rem,calc(100vw-1.5rem))] max-h-[calc(100vh-5rem)] overflow-y-auto rounded-xl bg-neutral-900/95 border border-white/10 shadow-2xl p-4 text-sm space-y-4"
         role="dialog" aria-label="放映设置" @click.stop @mousemove.stop>
      <label class="block">
        <span class="text-white/60 text-xs">放映内容</span>
        <select v-model="sourceDraft" @change="changeSource" class="mt-1 w-full bg-neutral-800 border border-white/10 rounded-lg px-2 py-1.5">
          <option value="best">精选（自动挑选清晰的好照片）</option>
          <option value="favorites">收藏</option>
          <optgroup v-if="sources.albums?.length" label="相册">
            <option v-for="a in sources.albums" :key="'a' + a.id" :value="'album:' + a.id">{{ a.name }}（{{ a.count }}）</option>
          </optgroup>
          <optgroup v-if="sources.people?.length" label="人物">
            <option v-for="p in sources.people" :key="'p' + p.id" :value="'person:' + p.id">{{ p.name }}</option>
          </optgroup>
          <optgroup v-if="sources.trips?.length" label="旅行">
            <option v-for="t in sources.trips" :key="'t' + t.id" :value="'trip:' + t.id">{{ t.title }}</option>
          </optgroup>
          <optgroup v-if="sources.years?.length" label="年份">
            <option v-for="y in sources.years" :key="'y' + y" :value="'year:' + y">{{ y }} 年</option>
          </optgroup>
          <option v-if="sourceDraft.startsWith('search:')" :value="sourceDraft">{{ label }}</option>
        </select>
      </label>
      <div>
        <span class="text-white/60 text-xs">每张停留</span>
        <div class="mt-1 flex flex-wrap gap-1.5">
          <button v-for="s in INTERVALS" :key="s" @click="settings.interval = s"
                  class="px-2.5 py-1 rounded-full border" :class="settings.interval === s ? 'border-blue-400 bg-blue-500/20' : 'border-white/15 hover:bg-white/10'">
            {{ s < 60 ? s + ' 秒' : s / 60 + ' 分钟' }}
          </button>
        </div>
      </div>
      <div class="grid grid-cols-2 gap-2">
        <label class="toggle"><input type="checkbox" v-model="settings.clock" /> 显示时钟</label>
        <label class="toggle"><input type="checkbox" v-model="settings.info" /> 地点和日期</label>
        <label class="toggle"><input type="checkbox" v-model="settings.kenBurns" /> 缓慢推近</label>
        <label class="toggle"><input type="checkbox" :checked="settings.fit === 'cover'" @change="settings.fit = $event.target.checked ? 'cover' : 'contain'" /> 铺满屏幕</label>
      </div>
      <label class="block">
        <span class="text-white/60 text-xs">顺序</span>
        <select v-model="settings.order" @change="reload" class="mt-1 w-full bg-neutral-800 border border-white/10 rounded-lg px-2 py-1.5">
          <option value="">自动（旅行和年份按时间，其余随机）</option>
          <option value="shuffle">随机</option>
          <option value="time">按拍摄时间</option>
        </select>
      </label>
      <p class="text-xs text-white/40 leading-relaxed">
        空格暂停，← → 切换，F 全屏，C 时钟，I 信息，Esc 退出。<span v-if="!wakeLockSupported">这个浏览器不支持保持屏幕常亮，请在系统设置里关闭自动锁屏。</span>
      </p>
    </div>
  </div>
</template>

<script setup>
/**
 * /frame — full-screen slideshow / digital photo frame.
 *
 * ?source=best | favorites | album:<id> | person:<id> | trip:<id> | year:<y> | search:<q>
 *
 * Photos come from /frame/photos (stills only; "best" skips blurry and
 * dark shots). Two stacked layers cross-fade; the next photo is fully
 * decoded before the swap so there is never a half-drawn frame. The
 * screen is kept awake (Wake Lock API) while playing. Display settings
 * are remembered in this browser.
 */
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { X, Play, Pause, SkipBack, SkipForward, Settings2, Maximize, Minimize } from 'lucide-vue-next'
import { API_BASE } from '../api/base'

const FADE_MS = 1200
const INTERVALS = [5, 10, 20, 30, 60, 300]
const STORE_KEY = 'deepphoto.frame'
const DEFAULTS = { interval: 10, clock: true, info: true, kenBurns: true, fit: 'contain', order: '' }

const route = useRoute()
const router = useRouter()

const loadSettings = () => {
  try { return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(STORE_KEY) || '{}') } } catch { return { ...DEFAULTS } }
}
const settings = reactive(loadSettings())
watch(settings, (s) => { try { localStorage.setItem(STORE_KEY, JSON.stringify(s)) } catch { /* private mode */ } }, { deep: true })

const items = ref([])
const label = ref('')
const index = ref(-1)
const randomOrder = ref(true)         // order the server actually used
const state = ref('loading')          // loading | playing | empty | error
const paused = ref(false)
const layers = reactive([{ src: '', item: null, origin: '50% 50%' }, { src: '', item: null, origin: '50% 50%' }])
const active = ref(0)
const chrome = ref(true)
const openPanel = ref(false)
const sources = ref({})
const sourceDraft = ref(route.query.source || 'best')
const isFullscreen = ref(!!document.fullscreenElement)
const canFullscreen = !!document.documentElement.requestFullscreen
const wakeLockSupported = typeof navigator !== 'undefined' && 'wakeLock' in navigator

const current = computed(() => layers[active.value].item)
const src = (p) => `${API_BASE}/files/thumbnail?path=${encodeURIComponent(p)}&size=preview`
const takenOn = (ts) => ts ? new Date(ts * 1000).toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' }) : ''

// ------------------------------------------------------------------ clock
const clock = reactive({ time: '', date: '' })
const tickClock = () => {
  const d = new Date()
  clock.time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  clock.date = d.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' })
}

// ------------------------------------------------------------------ playback
let timer = 0
let showSeq = 0
const ORIGINS = ['30% 30%', '70% 30%', '50% 50%', '30% 70%', '70% 70%']

const decode = (url) => new Promise((resolve, reject) => {
  const img = new Image()
  img.onload = () => (img.decode ? img.decode().catch(() => {}) : Promise.resolve()).then(() => resolve(url))
  img.onerror = reject
  img.src = url
})

const schedule = () => {
  clearTimeout(timer)
  if (!paused.value && items.value.length > 1) timer = setTimeout(() => step(1), settings.interval * 1000)
}

/** Show items[i]; skips over files that fail to load (in direction dir). */
const show = async (i, dir = 1, tries = 0) => {
  const n = items.value.length
  if (!n) return
  const k = ((i % n) + n) % n
  const mine = ++showSeq
  const item = items.value[k]
  try {
    const url = await decode(src(item.file_path))
    if (mine !== showSeq) return
    const next = 1 - active.value
    layers[next].src = url
    layers[next].item = item
    layers[next].origin = ORIGINS[Math.floor(Math.random() * ORIGINS.length)]
    active.value = next
    index.value = k
    state.value = 'playing'
    schedule()
    // warm the cache for the one after
    const after = items.value[(k + 1) % n]
    if (after) new Image().src = src(after.file_path)
  } catch (e) {
    if (mine !== showSeq) return
    if (tries + 1 < Math.min(n, 10)) return show(k + dir, dir, tries + 1)
    state.value = 'error'
  }
}

const step = (d) => {
  if (!items.value.length) return
  if (d > 0 && index.value === items.value.length - 1 && randomOrder.value) {
    reload()          // one full round done: new random order
    return
  }
  show(index.value + d, d < 0 ? -1 : 1)
}
const togglePause = () => {
  paused.value = !paused.value
  paused.value ? clearTimeout(timer) : schedule()
}
watch(() => settings.interval, schedule)

const load = async () => {
  state.value = 'loading'
  clearTimeout(timer)
  const source = route.query.source || 'best'
  sourceDraft.value = source
  try {
    const params = { source, seed: Math.floor(Math.random() * 1e9) }
    if (settings.order) params.order = settings.order
    const res = await axios.get(`${API_BASE}/frame/photos`, { params })
    items.value = res.data.items
    label.value = res.data.label
    randomOrder.value = res.data.order === 'shuffle' || res.data.order === 'weighted'
    index.value = -1
    if (!items.value.length) { state.value = 'empty'; return }
    await show(0)
  } catch (e) {
    state.value = 'error'
    label.value = ''
  }
}
const reload = () => load()

const changeSource = () => {
  router.replace({ query: { ...route.query, source: sourceDraft.value } })
}
watch(() => route.query.source, (s, old) => { if (s !== old) load() })

// ------------------------------------------------------------------ chrome
let hideTimer = 0
const poke = () => {
  chrome.value = true
  clearTimeout(hideTimer)
  hideTimer = setTimeout(() => { if (!openPanel.value) chrome.value = false }, 3000)
}
watch(openPanel, (o) => { if (!o) poke() })
const onTap = () => {
  if (openPanel.value) { openPanel.value = false; return }
  if (chrome.value) { chrome.value = false; clearTimeout(hideTimer) } else poke()
}
let touchX = null
const onTouchStart = (e) => { touchX = e.touches[0].clientX }
const onTouchEnd = (e) => {
  if (touchX == null) return
  const dx = e.changedTouches[0].clientX - touchX
  touchX = null
  if (Math.abs(dx) > 50) { e.preventDefault(); step(dx < 0 ? 1 : -1) }
}

const toggleFullscreen = async () => {
  try {
    if (document.fullscreenElement) await document.exitFullscreen()
    else await document.documentElement.requestFullscreen()
  } catch { /* not allowed */ }
}
const onFsChange = () => { isFullscreen.value = !!document.fullscreenElement }

const exit = async () => {
  if (document.fullscreenElement) { try { await document.exitFullscreen() } catch { /* ignore */ } }
  if (window.history.state?.back) router.back()
  else router.push('/timeline')
}

const onKey = (e) => {
  if (e.target.closest?.('select,input')) return
  const k = e.key
  if (k === ' ') { e.preventDefault(); togglePause() }
  else if (k === 'ArrowRight') step(1)
  else if (k === 'ArrowLeft') step(-1)
  else if (k === 'f' || k === 'F') toggleFullscreen()
  else if (k === 'c' || k === 'C') settings.clock = !settings.clock
  else if (k === 'i' || k === 'I') settings.info = !settings.info
  else if (k === 'Escape') { if (openPanel.value) openPanel.value = false; else exit() }
  else return
  poke()
}

// ------------------------------------------------------------------ wake lock
let wakeLock = null
const lockScreen = async () => {
  if (!wakeLockSupported || document.visibilityState !== 'visible' || wakeLock) return
  try {
    wakeLock = await navigator.wakeLock.request('screen')
    wakeLock.addEventListener('release', () => { wakeLock = null })
  } catch { /* battery saver, permissions… */ }
}
const onVisibility = () => { if (document.visibilityState === 'visible') lockScreen() }

let clockTimer = 0
onMounted(async () => {
  tickClock()
  clockTimer = setInterval(tickClock, 5000)
  window.addEventListener('keydown', onKey)
  document.addEventListener('fullscreenchange', onFsChange)
  document.addEventListener('visibilitychange', onVisibility)
  lockScreen()
  poke()
  load()
  try { sources.value = (await axios.get(`${API_BASE}/frame/sources`)).data } catch { /* panel shows the basics */ }
})
onBeforeUnmount(() => {
  clearTimeout(timer); clearTimeout(hideTimer); clearInterval(clockTimer)
  window.removeEventListener('keydown', onKey)
  document.removeEventListener('fullscreenchange', onFsChange)
  document.removeEventListener('visibilitychange', onVisibility)
  try { wakeLock?.release() } catch { /* ignore */ }
})
defineExpose({ items, index, paused, settings, step, togglePause, state, label })
</script>

<style scoped>
.ctl {
  width: 2.5rem; height: 2.5rem; flex-shrink: 0; border-radius: 9999px;
  display: flex; align-items: center; justify-content: center;
  background: rgb(0 0 0 / 0.35); color: white;
}
.ctl:hover { background: rgb(255 255 255 / 0.15); }
.toggle { display: flex; align-items: center; gap: 0.5rem; cursor: pointer; }
.toggle input { accent-color: #3b82f6; width: 1rem; height: 1rem; }
.kenburns {
  animation: kenburns var(--kb-ms, 12000ms) ease-out both;
  transform-origin: var(--kb-origin, 50% 50%);
}
@keyframes kenburns { from { transform: scale(1); } to { transform: scale(1.08); } }
@media (prefers-reduced-motion: reduce) { .kenburns { animation: none; } }
.fade-enter-active, .fade-leave-active { transition: opacity .3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
