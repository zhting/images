<template>
  <router-link to="/settings" class="block p-4 border-t border-line hover:bg-surface-hover transition-colors" :title="title">
    <div class="flex items-center gap-2 text-xs" :class="textClass">
      <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" :class="[dotClass, busy ? 'animate-pulse' : '']"></span>
      <span class="truncate">{{ label }}</span>
    </div>
    <div v-if="kind === 'indexing' && status.total" class="mt-2 h-1 bg-line rounded-full overflow-hidden">
      <div class="h-full bg-blue-500 rounded-full transition-all duration-500" :style="{ width: percent + '%' }"></div>
    </div>
  </router-link>
</template>

<script setup>
/**
 * Real backend / indexing status for the sidebar footer, replacing a
 * hard-coded green "在线" dot. Polls /index/status: every 1.5s while a scan
 * or index is running, every 10s otherwise, and not at all while the tab is
 * hidden. Clicking it opens Settings, where indexing is managed.
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import { API_BASE } from '../api/base'

const status = ref({})
const reachable = ref(true)
let timer = null

const kind = computed(() => {
  if (!reachable.value) return 'offline'
  const s = status.value.status
  if (s === 'scanning' || s === 'scanned') return 'scanning'
  if (s === 'indexing') return 'indexing'
  if (s === 'error') return 'error'
  return 'ready'
})
const busy = computed(() => kind.value === 'scanning' || kind.value === 'indexing')
const percent = computed(() =>
  status.value.total ? Math.min(100, Math.round((status.value.current / status.value.total) * 100)) : 0)

const label = computed(() => ({
  offline: '后端未连接',
  scanning: '正在扫描文件夹…',
  indexing: status.value.total ? `索引中 ${status.value.current} / ${status.value.total}` : '索引中…',
  error: '上次索引出错，点击查看',
  ready: '已就绪',
}[kind.value]))
const title = computed(() => (kind.value === 'error' ? status.value.phase : '') || label.value)
const dotClass = computed(() => ({
  offline: 'bg-red-500', scanning: 'bg-blue-500', indexing: 'bg-blue-500',
  error: 'bg-amber-500', ready: 'bg-green-500',
}[kind.value]))
const textClass = computed(() => (kind.value === 'offline' || kind.value === 'error') ? 'text-gray-400' : 'text-gray-500')

const poll = async () => {
  if (document.hidden) return schedule()
  try {
    status.value = (await axios.get(`${API_BASE}/index/status`, { timeout: 5000 })).data
    reachable.value = true
  } catch (e) {
    reachable.value = false
  }
  schedule()
}
const schedule = () => {
  clearTimeout(timer)
  timer = setTimeout(poll, busy.value ? 1500 : 10000)
}
const onVisible = () => { if (!document.hidden) poll() }

onMounted(() => {
  poll()
  document.addEventListener('visibilitychange', onVisible)
})
onUnmounted(() => {
  clearTimeout(timer)
  document.removeEventListener('visibilitychange', onVisible)
})

defineExpose({ kind, label })
</script>
