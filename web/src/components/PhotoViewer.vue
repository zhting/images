<template>
  <div class="fixed inset-0 z-50 bg-black/95 flex flex-col" tabindex="0">
    <!-- Toolbar -->
    <div class="flex justify-between items-center p-4 text-white bg-black/50 backdrop-blur-sm z-30 absolute top-0 left-0 right-0">
      <div class="flex items-center gap-4">
        <span class="font-mono">{{ currentIndex + 1 }} / {{ items.length }}</span>
        <slot name="toolbar" :current="current" />
      </div>

      <div class="flex items-center gap-4">
        <button @click="toggleInfo" class="p-2 rounded hover:bg-white/10"
                :class="showInfo ? 'text-blue-400' : 'text-white hover:text-blue-400'" title="信息 (I)">
          <Info :size="22" />
        </button>
        <button @click="revealInExplorer" class="text-white hover:text-blue-400 p-2 rounded hover:bg-white/10" title="在资源管理器中显示">
          <FolderOpen :size="22" />
        </button>
        <button v-if="allowTrash" @click="requestTrash" class="text-white hover:text-red-400 p-2 rounded hover:bg-white/10" title="移入回收站">
          <Trash2 :size="22" />
        </button>
        <button @click="$emit('close')" class="text-2xl font-bold p-2 hover:bg-white/20 rounded w-10 h-10 flex items-center justify-center">✕</button>
      </div>
    </div>

    <!-- Main Image/Video + optional info panel -->
    <div class="flex-1 flex relative overflow-hidden">
      <div class="flex-1 flex items-center justify-center relative overflow-hidden"
           @wheel.prevent="onWheel" @dblclick="onDblClick"
           @pointerdown="onPointerDown" @pointermove="onPointerMove"
           @pointerup="onPointerUp" @pointercancel="onPointerUp">
        <button @click="prev" class="absolute left-4 z-20 text-white text-4xl p-4 hover:bg-white/10 rounded-full" v-if="currentIndex > 0 && zoom === 1">❮</button>

        <video v-if="isVideo" :src="fileUrl(current.file_path)" controls autoplay class="max-h-full max-w-full outline-none"></video>
        <img v-else-if="currentImage" :src="currentImage"
             class="max-h-full max-w-full object-contain select-none"
             :class="zoom > 1 ? 'cursor-grab' : ''"
             :style="{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`, transition: dragging ? 'none' : 'transform 0.15s ease' }"
             draggable="false" />

        <button @click="next" class="absolute right-4 z-20 text-white text-4xl p-4 hover:bg-white/10 rounded-full" v-if="currentIndex < items.length - 1 && zoom === 1">❯</button>

        <div v-if="zoom > 1" class="absolute bottom-3 left-1/2 -translate-x-1/2 bg-black/60 text-white/80 text-xs px-2 py-1 rounded z-20">
          {{ Math.round(zoom * 100) }}% · 双击复原
        </div>
      </div>

      <!-- Info panel -->
      <div v-if="showInfo" class="w-72 flex-shrink-0 bg-[#141414] border-l border-[#222] p-5 overflow-y-auto text-sm">
        <h3 class="text-white font-medium mb-4 truncate" :title="info?.basename">{{ info?.basename || '…' }}</h3>
        <template v-if="info">
          <div class="space-y-2 text-gray-400">
            <div v-if="info.captured_time" class="flex justify-between gap-2">
              <span class="text-gray-500">拍摄时间</span>
              <span class="text-right">{{ formatTime(info.captured_time) }}</span>
            </div>
            <div v-if="info.width" class="flex justify-between gap-2">
              <span class="text-gray-500">尺寸</span><span>{{ info.width }} × {{ info.height }}</span>
            </div>
            <div class="flex justify-between gap-2">
              <span class="text-gray-500">大小</span><span>{{ formatSize(info.size_bytes) }}</span>
            </div>
            <div v-if="cameraLine" class="flex justify-between gap-2">
              <span class="text-gray-500">相机</span><span class="text-right">{{ cameraLine }}</span>
            </div>
            <div v-if="exposureLine" class="flex justify-between gap-2">
              <span class="text-gray-500">参数</span><span class="text-right">{{ exposureLine }}</span>
            </div>
            <div v-if="locationLine" class="flex justify-between gap-2">
              <span class="text-gray-500">地点</span><span class="text-right">{{ locationLine }}</span>
            </div>
          </div>
          <div v-if="info.auto_tags && info.auto_tags.length" class="mt-4">
            <div class="text-gray-500 mb-1.5">AI 标签</div>
            <div class="flex flex-wrap gap-1.5">
              <span v-for="t in info.auto_tags" :key="t"
                    class="bg-[#222] text-gray-300 text-xs px-2 py-0.5 rounded-full">{{ t }}</span>
            </div>
          </div>
          <div class="mt-4 text-gray-600 text-xs break-all" :title="info.file_path">{{ info.file_path }}</div>
        </template>
        <div v-else class="text-gray-600 animate-pulse">加载中…</div>
      </div>
    </div>

    <!-- Filmstrip -->
    <div class="h-24 bg-black/80 flex items-center gap-2 overflow-x-auto p-2" ref="strip">
      <div
        v-for="(item, idx) in items"
        :key="'pv-thumb-' + item.file_path"
        class="h-full aspect-square flex-shrink-0 cursor-pointer border-2 relative"
        :class="idx === currentIndex ? 'border-red-500' : 'border-transparent opacity-60 hover:opacity-100'"
        @click="go(idx)"
        :id="'pv-thumb-' + idx"
      >
        <img :src="thumbUrl(item.file_path)" class="h-full w-full object-cover" />
        <slot name="thumb-badge" :item="item" />
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * Shared photo viewer — single implementation of what used to be four
 * near-copies (Timeline / BestShots / Folders / OnThisDay).
 *
 * Contract: the parent owns the item array and its mutations. The
 * viewer emits `trash(item)` and the parent performs the API call and
 * splices the array; the viewer reacts to length changes (clamps the
 * index, closes when empty). Progressive loading, neighbor preloading,
 * keyboard navigation and the filmstrip live here once.
 */
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { FolderOpen, Trash2, Info } from 'lucide-vue-next'
import axios from 'axios'

const props = defineProps({
  items: { type: Array, required: true },
  startIndex: { type: Number, default: 0 },
  apiBase: { type: String, default: 'http://localhost:8001' },
  token: { type: String, default: '' },       // privacy session (Folders)
  allowTrash: { type: Boolean, default: true },
})
const emit = defineEmits(['close', 'trash', 'index-change'])

const currentIndex = ref(Math.min(props.startIndex, props.items.length - 1))
const currentImage = ref('')
const strip = ref(null)

const current = computed(() => props.items[currentIndex.value])
const isVideo = computed(() => current.value && current.value.tag === 'video')

const withToken = (url) =>
  props.token ? `${url}&token=${encodeURIComponent(props.token)}` : url
const thumbUrl = (p, size = 'grid') =>
  withToken(`${props.apiBase}/files/thumbnail?path=${encodeURIComponent(p)}&size=${size}`)
const fileUrl = (p) =>
  withToken(`${props.apiBase}/files/content?path=${encodeURIComponent(p)}`)

// Progressive display: cached grid thumb instantly -> preview swap ->
// original in the background. Stale loads discarded via still-current.
const loadProgressive = (item) => {
  if (!item || item.tag === 'video') return
  const gridUrl = thumbUrl(item.file_path, 'grid')
  const previewUrl = thumbUrl(item.file_path, 'preview')
  const originalUrl = fileUrl(item.file_path)
  currentImage.value = gridUrl

  const stillCurrent = () => current.value === item

  const preview = new Image()
  preview.src = previewUrl
  preview.onload = () => {
    if (stillCurrent() && currentImage.value !== originalUrl) {
      currentImage.value = previewUrl
    }
  }
  const original = new Image()
  original.src = originalUrl
  original.onload = () => {
    if (stillCurrent()) currentImage.value = originalUrl
  }
}

const preloadNeighbors = () => {
  ;[currentIndex.value - 1, currentIndex.value + 1].forEach((i) => {
    const it = props.items[i]
    if (it && it.tag !== 'video') {
      const img = new Image()
      img.src = thumbUrl(it.file_path, 'preview')
    }
  })
}

const scrollToThumb = () => {
  nextTick(() => {
    const el = document.getElementById('pv-thumb-' + currentIndex.value)
    if (el && strip.value) {
      el.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
    }
  })
}

// ---------------- Zoom & pan ----------------
const zoom = ref(1)
const pan = ref({ x: 0, y: 0 })
const dragging = ref(false)
let dragStart = null

const resetZoom = () => { zoom.value = 1; pan.value = { x: 0, y: 0 } }

const onWheel = (e) => {
  if (isVideo.value) return
  const next = Math.min(6, Math.max(1, zoom.value * (e.deltaY < 0 ? 1.2 : 1 / 1.2)))
  zoom.value = next
  if (next === 1) pan.value = { x: 0, y: 0 }
}

const onDblClick = () => {
  if (isVideo.value) return
  if (zoom.value > 1) resetZoom()
  else zoom.value = 2.5
}

const onPointerDown = (e) => {
  if (zoom.value === 1) return
  dragging.value = true
  dragStart = { x: e.clientX - pan.value.x, y: e.clientY - pan.value.y }
  e.target.setPointerCapture?.(e.pointerId)
}
const onPointerMove = (e) => {
  if (!dragging.value || !dragStart) return
  pan.value = { x: e.clientX - dragStart.x, y: e.clientY - dragStart.y }
}
const onPointerUp = () => { dragging.value = false; dragStart = null }

// ---------------- Info panel ----------------
const showInfo = ref(false)
const info = ref(null)

const toggleInfo = () => {
  showInfo.value = !showInfo.value
  if (showInfo.value) fetchInfo()
}

const fetchInfo = async () => {
  info.value = null
  if (!current.value) return
  try {
    const res = await axios.get(`${props.apiBase}/files/info`, {
      params: props.token
        ? { path: current.value.file_path, token: props.token }
        : { path: current.value.file_path },
    })
    info.value = res.data
  } catch (e) {
    info.value = { basename: current.value.file_path.split('/').pop(),
                   file_path: current.value.file_path, size_bytes: 0, exif: {} }
  }
}

const cameraLine = computed(() => {
  const e = info.value?.exif || {}
  return [e.make, e.model].filter(Boolean).join(' ')
})
const exposureLine = computed(() => {
  const e = info.value?.exif || {}
  const iso = e.iso ? `ISO${e.iso}` : ''
  return [e.f_number, e.exposure_time, e.focal_length, iso].filter(Boolean).join(' · ')
})
const locationLine = computed(() => {
  const l = info.value?.location || {}
  return [l.city, l.province].filter(Boolean).join('，')
})
const formatSize = (b) => {
  if (!b) return '—'
  if (b > 1024 * 1024) return (b / 1024 / 1024).toFixed(1) + ' MB'
  return Math.round(b / 1024) + ' KB'
}
const formatTime = (t) => new Date(t * 1000).toLocaleString('zh-CN', { hour12: false })

const refresh = () => {
  resetZoom()
  if (showInfo.value) fetchInfo()
  loadProgressive(current.value)
  scrollToThumb()
  preloadNeighbors()
  emit('index-change', currentIndex.value)
}

const go = (idx) => { currentIndex.value = idx; refresh() }
const prev = () => { if (currentIndex.value > 0) go(currentIndex.value - 1) }
const next = () => { if (currentIndex.value < props.items.length - 1) go(currentIndex.value + 1) }

const requestTrash = () => { if (current.value) emit('trash', current.value) }

const revealInExplorer = async () => {
  if (!current.value) return
  try {
    await axios.post(`${props.apiBase}/system/explorer`, { path: current.value.file_path })
  } catch (e) {
    console.error('Failed to reveal in explorer', e)
  }
}

// Parent mutated the array (e.g. after trash) — clamp or close.
watch(() => props.items.length, (len) => {
  if (len === 0) { emit('close'); return }
  if (currentIndex.value >= len) currentIndex.value = len - 1
  refresh()
})

const handleKey = (e) => {
  if (e.key === 'ArrowLeft') prev()
  if (e.key === 'ArrowRight') next()
  if (e.key === 'Escape') { if (zoom.value > 1) { resetZoom(); return } emit('close') }
  if (e.key === 'i' || e.key === 'I') toggleInfo()
  if ((e.key === 'Delete' || e.key === 'Backspace') && props.allowTrash) requestTrash()
}

onMounted(() => {
  window.addEventListener('keydown', handleKey)
  document.body.style.overflow = 'hidden'
  refresh()
})
onUnmounted(() => {
  window.removeEventListener('keydown', handleKey)
  document.body.style.overflow = ''
})
</script>
