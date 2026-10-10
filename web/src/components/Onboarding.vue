<template>
  <div :class="compact ? 'mb-6' : 'flex-1 flex items-center justify-center p-4 sm:p-8'">
    <div class="w-full bg-surface-raised border border-line rounded-2xl text-center shadow-2xl"
         :class="compact ? 'max-w-3xl mx-auto p-5' : 'max-w-lg p-8'">

      <!-- Welcome: pick a folder -->
      <template v-if="step === 'welcome'">
        <div class="flex justify-center mb-5">
          <ImageIcon :size="52" :stroke-width="1.2" class="text-blue-500" />
        </div>
        <h2 class="text-2xl font-bold text-content mb-3">欢迎使用 Deep Photo</h2>
        <p class="text-gray-400 mb-2 leading-relaxed">
          选择一个照片文件夹，AI 会在本地为它建立索引。之后你就可以用自然语言搜索照片——比如「海边的日落」或「猫在沙发上」。
        </p>
        <p class="text-gray-500 text-sm mb-8">
          所有处理都在你的设备上完成，照片不会上传。首次使用需下载约 3GB 的 AI 模型（仅此一次）。
        </p>
        <button
          @click="showBrowser = true"
          class="bg-blue-600 hover:bg-blue-500 text-white font-medium px-8 py-3 rounded-xl transition-colors inline-flex items-center gap-2">
          <FolderOpen :size="18" /> 选择照片文件夹
        </button>
        <p v-if="error" class="text-red-400 text-sm mt-4">{{ error }}</p>
      </template>

      <!-- Working: scanning or indexing -->
      <template v-else-if="step === 'working'">
        <div class="flex items-center gap-4" :class="compact ? 'text-left' : 'flex-col'">
          <Loader2 :size="compact ? 28 : 44" :stroke-width="1.5" class="text-blue-500 animate-spin flex-shrink-0" />
          <div class="min-w-0 w-full">
            <h2 class="font-bold text-content" :class="compact ? 'text-base' : 'text-xl mb-2'">{{ phaseTitle }}</h2>
            <p class="text-gray-400 text-sm truncate" :class="compact ? '' : 'mb-6 px-4'">{{ phaseDetail }}</p>
            <div v-if="status.total > 0" :class="compact ? 'mt-2' : 'mb-3'">
              <div class="h-2 bg-line rounded-full overflow-hidden">
                <div class="h-full bg-blue-500 rounded-full transition-all duration-500"
                     :style="{ width: percent + '%' }"></div>
              </div>
              <div class="flex justify-between text-xs text-gray-500 mt-2">
                <span>{{ status.current }} / {{ status.total }}</span>
                <span v-if="eta">约剩 {{ eta }}</span>
              </div>
            </div>
          </div>
        </div>
        <p v-if="!compact" class="text-gray-500 text-xs mt-6">
          索引进行中就可以浏览已入库的照片，页面会自动刷新。
        </p>
      </template>

      <!-- Nothing to index in that folder -->
      <template v-else-if="step === 'empty'">
        <div class="flex justify-center mb-4">
          <ImageOff :size="44" :stroke-width="1.3" class="text-gray-500" />
        </div>
        <h2 class="text-xl font-bold text-content mb-2">这个文件夹里没有找到照片</h2>
        <p class="text-gray-400 text-sm mb-6">支持 JPG、PNG、WEBP、HEIC 照片和 MP4、MOV、AVI、MKV 视频（包含子文件夹）。</p>
        <button @click="showBrowser = true"
                class="bg-blue-600 hover:bg-blue-500 text-white font-medium px-6 py-2.5 rounded-xl transition-colors inline-flex items-center gap-2">
          <FolderOpen :size="18" /> 换一个文件夹
        </button>
      </template>

      <!-- Failed or stopped: say why, offer a way forward -->
      <template v-else-if="step === 'failed'">
        <div class="flex justify-center mb-4">
          <AlertTriangle :size="44" :stroke-width="1.3" class="text-amber-500" />
        </div>
        <h2 class="text-xl font-bold text-content mb-2">{{ stopped ? '索引已停止' : '索引没有完成' }}</h2>
        <p class="text-gray-400 text-sm mb-6 break-words">{{ error || '请重试，或换一个文件夹。' }}</p>
        <div class="flex justify-center gap-3 flex-wrap">
          <button @click="retry"
                  class="bg-blue-600 hover:bg-blue-500 text-white font-medium px-6 py-2.5 rounded-xl transition-colors inline-flex items-center gap-2">
            <RotateCw :size="16" /> {{ stopped ? '继续索引' : '重试' }}
          </button>
          <button @click="showBrowser = true"
                  class="border border-line-strong hover:bg-surface-hover text-gray-300 px-6 py-2.5 rounded-xl transition-colors">
            换一个文件夹
          </button>
        </div>
      </template>
    </div>

    <FileBrowserModal
      v-model="showBrowser"
      mode="folder"
      :api-base="apiBase"
      @select="onFolderPicked"
    />
  </div>
</template>

<script setup>
import { API_BASE } from '../api/base'
/**
 * First-run onboarding: pick folder -> add path -> scan -> index, with
 * live progress and incremental refresh so photos appear as they are
 * indexed.
 *
 * The flow follows the backend's progress states exactly
 *   scanning -> scanned -> (POST /index/run) -> indexing -> completed
 *   ... or error / stopped at any point
 * and never reports success it did not observe. It also attaches to a run
 * that is already in progress when it mounts, so reloading the page or
 * navigating away and back keeps the progress visible.
 *
 * Emits:
 *   active(bool) — true while a run is in progress or needs attention;
 *                  the timeline keeps this card on screen while true.
 *   refresh      — newly indexed photos are available.
 *   done         — the run finished.
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import { FolderOpen, Image as ImageIcon, ImageOff, Loader2, AlertTriangle, RotateCw } from 'lucide-vue-next'
import FileBrowserModal from './FileBrowserModal.vue'
import { toast } from '../composables/useToast'

const props = defineProps({
  apiBase: { type: String, default: API_BASE },
  compact: { type: Boolean, default: false },   // slim banner above an existing timeline
})
const emit = defineEmits(['refresh', 'done', 'active'])

const step = ref('welcome')          // welcome | working | empty | failed
const showBrowser = ref(false)
const error = ref('')
const stopped = ref(false)
const status = ref({ status: 'idle', phase: '', current: 0, total: 0, current_file: '' })

let pollTimer = null
let pollCount = 0
let startedIndexing = false

const percent = computed(() =>
  status.value.total ? Math.min(100, Math.round((status.value.current / status.value.total) * 100)) : 0)

const phaseTitle = computed(() => {
  const s = status.value.status
  if (s === 'scanning' || s === 'idle') return '正在扫描文件夹…'
  if (s === 'scanned') return '扫描完成，正在启动索引…'
  return '正在建立 AI 索引…'
})
const phaseDetail = computed(() =>
  status.value.current_file || status.value.phase || '准备中…')

const eta = computed(() => {
  const s = status.value
  if (!s.start_time || !s.current || !s.total) return ''
  const elapsed = Date.now() / 1000 - s.start_time
  const remain = (elapsed / s.current) * (s.total - s.current)
  if (!isFinite(remain) || remain <= 0) return ''
  if (remain < 90) return `${Math.ceil(remain)} 秒`
  return `${Math.ceil(remain / 60)} 分钟`
})

const errorText = (e, fallback) =>
  e?.response?.data?.message || e?.response?.data?.detail || fallback

const setStep = (next) => {
  step.value = next
  emit('active', next !== 'welcome')
}

const fail = (message, wasStopped = false) => {
  stopPolling()
  error.value = message
  stopped.value = wasStopped
  setStep('failed')
}

const finish = () => {
  stopPolling()
  const n = status.value.total || status.value.current
  toast(n ? `索引完成，共处理 ${n} 个文件` : '索引完成', { duration: 5000 })
  emit('refresh')
  emit('done')
  setStep('welcome')   // the timeline hides this card once it has photos
}

const startIndexing = async () => {
  startedIndexing = true
  try {
    await axios.post(`${props.apiBase}/index/run`, { force: false })
  } catch (e) {
    // 400 "already in progress" means someone else started it: keep polling.
    if (e?.response?.status !== 400) fail(errorText(e, '无法启动索引'))
  }
}

const poll = async () => {
  let s
  try {
    s = (await axios.get(`${props.apiBase}/index/status`)).data
  } catch (e) {
    return  // transient (backend busy/restarting); try again next tick
  }
  status.value = s
  pollCount++

  switch (s.status) {
    case 'scanning':
      return
    case 'indexing':
      // Photos become browsable while indexing — refresh the timeline
      // every ~15s so it fills in behind the card.
      if (pollCount % 10 === 0) emit('refresh')
      return
    case 'scanned': {
      if (startedIndexing) return            // waiting for the run to begin
      if (!s.scan_result || !s.scan_result.total_ops) {
        stopPolling()
        setStep('empty')
        return
      }
      await startIndexing()
      return
    }
    case 'completed':
      finish()
      return
    case 'stopped':
      fail('索引在完成前被停止了。已入库的照片不受影响。', true)
      return
    case 'error':
      fail(s.phase || '索引过程中出现错误')
      return
    default:
      // 'idle' right after we asked for a scan: the task has not reported
      // yet. Give it a few ticks before deciding nothing is happening.
      if (pollCount > 20) fail('扫描没有开始，请重试。')
  }
}

const startPolling = () => {
  stopPolling()
  pollCount = 0
  poll()
  pollTimer = setInterval(poll, 1500)
}
const stopPolling = () => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

const beginScan = async () => {
  error.value = ''
  stopped.value = false
  startedIndexing = false
  setStep('working')
  try {
    await axios.get(`${props.apiBase}/index/scan`)
  } catch (e) {
    // 400 = a scan or run is already going; just follow it.
    if (e?.response?.status !== 400) { fail(errorText(e, '无法开始扫描')); return }
  }
  startPolling()
}

const onFolderPicked = async (path) => {
  error.value = ''
  try {
    await axios.post(`${props.apiBase}/config/paths`, { path })
  } catch (e) {
    error.value = errorText(e, '添加文件夹失败，请重试')
    if (step.value === 'working') setStep('welcome')
    return
  }
  await beginScan()
}

// Retry and "continue" are the same operation: a fresh scan only picks up
// what is not indexed yet.
const retry = () => beginScan()

onMounted(async () => {
  // Re-attach to a run already in progress (page reload, navigation).
  try {
    const s = (await axios.get(`${props.apiBase}/index/status`)).data
    if (['scanning', 'scanned', 'indexing'].includes(s.status)) {
      status.value = s
      startedIndexing = s.status === 'indexing'
      setStep('working')
      startPolling()
    }
  } catch (e) { /* backend not reachable yet: stay on welcome */ }
})

onUnmounted(stopPolling)

defineExpose({ step, status })
</script>
