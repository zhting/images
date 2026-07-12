<template>
  <div class="flex-1 flex items-center justify-center p-8">
    <div class="max-w-lg w-full bg-[#141414] border border-[#222] rounded-2xl p-8 text-center shadow-2xl">

      <!-- Step 1: Welcome -->
      <template v-if="step === 'welcome'">
        <div class="flex justify-center mb-5">
          <ImageIcon :size="52" :stroke-width="1.2" class="text-blue-500" />
        </div>
        <h2 class="text-2xl font-bold text-white mb-3">欢迎使用 Deep Photo</h2>
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

      <!-- Step 2: Working (scan + index) -->
      <template v-else>
        <div class="flex justify-center mb-5">
          <Loader2 :size="44" :stroke-width="1.5" class="text-blue-500 animate-spin" />
        </div>
        <h2 class="text-xl font-bold text-white mb-2">{{ phaseTitle }}</h2>
        <p class="text-gray-400 text-sm mb-6 truncate px-4">{{ status.phase || status.current_file || '准备中…' }}</p>

        <div v-if="status.total > 0" class="mb-3">
          <div class="h-2 bg-[#222] rounded-full overflow-hidden">
            <div class="h-full bg-blue-500 rounded-full transition-all duration-500"
                 :style="{ width: percent + '%' }"></div>
          </div>
          <div class="flex justify-between text-xs text-gray-500 mt-2">
            <span>{{ status.current }} / {{ status.total }}</span>
            <span v-if="eta">约剩 {{ eta }}</span>
          </div>
        </div>

        <p class="text-gray-500 text-xs mt-6">
          索引进行中就可以浏览已入库的照片，页面会自动刷新。
        </p>
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
/**
 * First-run onboarding: an app that needs an index before it can show
 * anything must make building that index its front door — not a
 * four-step trail hidden in Settings. Flow: pick folder -> add path ->
 * scan -> index, with live progress and incremental refresh so the
 * waiting period has feedback (photos appear as they are indexed).
 */
import { ref, computed, onUnmounted } from 'vue'
import axios from 'axios'
import { FolderOpen, Image as ImageIcon, Loader2 } from 'lucide-vue-next'
import FileBrowserModal from './FileBrowserModal.vue'
import { toast } from '../composables/useToast'

const props = defineProps({
  apiBase: { type: String, default: 'http://localhost:8001' },
})
const emit = defineEmits(['refresh', 'done'])

const step = ref('welcome')          // welcome | working
const showBrowser = ref(false)
const error = ref('')
const status = ref({ status: 'idle', phase: '', current: 0, total: 0, current_file: '' })
let pollTimer = null
let refreshCounter = 0

const percent = computed(() =>
  status.value.total ? Math.min(100, Math.round((status.value.current / status.value.total) * 100)) : 0)

const phaseTitle = computed(() =>
  status.value.status === 'scanning' ? '正在扫描文件夹…' : '正在建立 AI 索引…')

const eta = computed(() => {
  const s = status.value
  if (!s.start_time || !s.current || !s.total) return ''
  const elapsed = Date.now() / 1000 - s.start_time
  const remain = (elapsed / s.current) * (s.total - s.current)
  if (!isFinite(remain) || remain <= 0) return ''
  if (remain < 90) return `${Math.ceil(remain)} 秒`
  return `${Math.ceil(remain / 60)} 分钟`
})

const poll = async () => {
  try {
    const res = await axios.get(`${props.apiBase}/index/status`)
    status.value = res.data

    // Photos become browsable while indexing — refresh the parent
    // every ~10 polls so the timeline fills in behind the card.
    if (++refreshCounter % 10 === 0) emit('refresh')

    if (status.value.status === 'scanning') return
    if (status.value.status === 'indexing') return

    // idle again: scan just finished -> kick off the run; or run done.
    if (status.value.scan_result && !startedIndexing) {
      startedIndexing = true
      await axios.post(`${props.apiBase}/index/run`)
      return
    }
    // Finished.
    stopPolling()
    toast('索引完成', { duration: 5000 })
    emit('refresh')
    emit('done')
  } catch (e) {
    // transient poll failures are fine; keep trying
  }
}

let startedIndexing = false

const startPolling = () => {
  stopPolling()
  pollTimer = setInterval(poll, 1500)
}
const stopPolling = () => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

const onFolderPicked = async (path) => {
  error.value = ''
  try {
    await axios.post(`${props.apiBase}/config/paths`, { path })
    step.value = 'working'
    startedIndexing = false
    await axios.get(`${props.apiBase}/index/scan`)
    startPolling()
  } catch (e) {
    error.value = e.response?.data?.message || e.response?.data?.detail || '添加文件夹失败，请重试'
  }
}

onUnmounted(stopPolling)
</script>
