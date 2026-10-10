<template>
  <div class="mb-4 pb-4 border-b border-line-strong">
    <div class="flex items-center justify-between gap-4">
      <div>
        <div class="text-sm font-medium text-gray-300">照片文字识别</div>
        <div class="text-xs text-gray-500 mt-0.5">
          在本机识别截图、文档和照片里的文字，用于搜索和复制。不需要联网，索引照片时会自动暂停。
        </div>
      </div>
      <label v-if="status && status.available" class="inline-flex items-center gap-2 cursor-pointer flex-shrink-0">
        <input type="checkbox" class="w-4 h-4 accent-blue-500" :checked="status.state !== 'disabled'"
               :disabled="saving" @change="toggle($event.target.checked)" />
        <span class="text-sm text-gray-400">{{ status.state === 'disabled' ? '已关闭' : '开启' }}</span>
      </label>
    </div>
    <div v-if="status" class="mt-2 text-xs text-gray-500">
      <template v-if="!status.available">未安装文字识别组件（rapidocr_onnxruntime），重新安装依赖后即可使用。</template>
      <template v-else>
        {{ stateLabel }} · 已识别 {{ status.done }} 张<template v-if="status.pending">，还剩 {{ status.pending }} 张</template>
        <span v-if="status.current" class="ml-1 text-gray-600">（{{ status.current }}）</span>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import { API_BASE } from '../api/base'

const status = ref(null)
const saving = ref(false)
let timer = null

const stateLabel = computed(() => ({
  running: '正在识别', paused: '索引进行中，已暂停', idle: '空闲', disabled: '已关闭',
}[status.value?.state] || ''))

const load = async () => {
  try { status.value = (await axios.get(`${API_BASE}/ocr/status`)).data } catch (e) { /* ignore */ }
}
const toggle = async (enabled) => {
  saving.value = true
  try { status.value = (await axios.post(`${API_BASE}/ocr/config`, { enabled })).data }
  finally { saving.value = false }
}

onMounted(() => { load(); timer = setInterval(load, 5000) })
onUnmounted(() => clearInterval(timer))
</script>
