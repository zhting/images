<template>
  <div class="fixed inset-0 z-50 bg-black/95 flex flex-col" tabindex="0">
    <!-- Toolbar -->
    <div class="flex justify-between items-center p-4 text-white bg-black/50 backdrop-blur-sm z-30 absolute top-0 left-0 right-0">
      <div class="flex items-center gap-4">
        <span class="font-mono">{{ currentIndex + 1 }} / {{ items.length }}</span>
        <slot name="toolbar" :current="current" />
      </div>

      <div class="flex items-center gap-4">
        <button @click="revealInExplorer" class="text-white hover:text-blue-400 p-2 rounded hover:bg-white/10" title="在资源管理器中显示">
          <FolderOpen :size="22" />
        </button>
        <button v-if="allowTrash" @click="requestTrash" class="text-white hover:text-red-400 p-2 rounded hover:bg-white/10" title="移入回收站">
          <Trash2 :size="22" />
        </button>
        <button @click="$emit('close')" class="text-2xl font-bold p-2 hover:bg-white/20 rounded w-10 h-10 flex items-center justify-center">✕</button>
      </div>
    </div>

    <!-- Main Image/Video -->
    <div class="flex-1 flex items-center justify-center relative overflow-hidden">
      <button @click="prev" class="absolute left-4 z-20 text-white text-4xl p-4 hover:bg-white/10 rounded-full" v-if="currentIndex > 0">❮</button>

      <video v-if="isVideo" :src="fileUrl(current.file_path)" controls autoplay class="max-h-full max-w-full outline-none"></video>
      <img v-else-if="currentImage" :src="currentImage" class="max-h-full max-w-full object-contain select-none" />

      <button @click="next" class="absolute right-4 z-20 text-white text-4xl p-4 hover:bg-white/10 rounded-full" v-if="currentIndex < items.length - 1">❯</button>
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
import { FolderOpen, Trash2 } from 'lucide-vue-next'
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

const refresh = () => {
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
  if (e.key === 'Escape') emit('close')
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
