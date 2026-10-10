<template>
  <div v-if="modelValue" class="fixed inset-0 z-[5500] bg-black/70 flex items-end sm:items-center justify-center p-0 sm:p-4"
       @click.self="close">
    <div class="bg-surface-raised border border-line-strong w-full sm:max-w-md rounded-t-2xl sm:rounded-2xl shadow-2xl flex flex-col max-h-[80vh]">
      <div class="flex items-center justify-between px-5 py-4 border-b border-line">
        <h3 class="text-content font-medium">加入相册<span v-if="count" class="text-gray-500 font-normal text-sm ml-2">{{ count }} 张</span></h3>
        <button @click="close" class="text-gray-500 hover:text-gray-300 p-1" aria-label="关闭"><X :size="18" /></button>
      </div>

      <!-- New album -->
      <form class="flex gap-2 px-5 py-3 border-b border-line" @submit.prevent="createAndPick">
        <input ref="nameInput" v-model.trim="newName" maxlength="60" placeholder="新相册名称"
               class="flex-1 bg-surface-sunken border border-line-strong rounded-lg px-3 py-2 text-sm text-content outline-none focus:border-blue-500" />
        <button type="submit" :disabled="!newName || busy"
                class="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-sm px-4 rounded-lg whitespace-nowrap">
          新建并加入
        </button>
      </form>

      <!-- Existing albums -->
      <div class="overflow-y-auto p-2">
        <div v-if="loading" class="text-center text-gray-500 text-sm py-8 animate-pulse">加载中…</div>
        <div v-else-if="error" class="text-center text-sm py-8">
          <p class="text-gray-400 mb-3">相册列表加载失败</p>
          <button @click="load" class="text-blue-400 hover:text-blue-300">重试</button>
        </div>
        <div v-else-if="!albums.length" class="text-center text-gray-500 text-sm py-8">还没有相册，在上面输入名称新建一个。</div>
        <button v-for="a in albums" :key="a.id" @click="pick(a)" :disabled="busy"
                class="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-surface-hover text-left disabled:opacity-50">
          <div class="w-11 h-11 rounded-md overflow-hidden bg-surface-sunken flex-shrink-0 flex items-center justify-center">
            <img v-if="a.cover" :src="`${apiBase}/files/thumbnail?path=${encodeURIComponent(a.cover)}`"
                 class="w-full h-full object-cover" loading="lazy" />
            <Library v-else :size="18" class="text-gray-600" />
          </div>
          <div class="min-w-0">
            <div class="text-sm text-content truncate">{{ a.name }}</div>
            <div class="text-xs text-gray-500">{{ a.count }} 张</div>
          </div>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * Pick an existing album or create one. Replaces a window.prompt() that
 * asked people to type an album's list number.
 *
 * v-model controls visibility; emits `pick(album)` with {id, name, ...}.
 * The caller performs the actual add so it can report the result.
 */
import { ref, watch, nextTick, onUnmounted } from 'vue'
import axios from 'axios'
import { Library, X } from 'lucide-vue-next'
import { API_BASE } from '../api/base'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  count: { type: Number, default: 0 },
  apiBase: { type: String, default: API_BASE },
})
const emit = defineEmits(['update:modelValue', 'pick'])

const albums = ref([])
const loading = ref(false)
const error = ref(false)
const busy = ref(false)
const newName = ref('')
const nameInput = ref(null)

const load = async () => {
  loading.value = true
  error.value = false
  try {
    albums.value = (await axios.get(`${props.apiBase}/albums`)).data || []
  } catch (e) {
    error.value = true
  } finally {
    loading.value = false
  }
}

const close = () => emit('update:modelValue', false)

const pick = (album) => {
  emit('pick', album)
  close()
}

const createAndPick = async () => {
  if (!newName.value) return
  busy.value = true
  try {
    const album = (await axios.post(`${props.apiBase}/albums`, { name: newName.value })).data
    pick(album)
  } catch (e) {
    error.value = true
  } finally {
    busy.value = false
  }
}

const onKey = (e) => { if (e.key === 'Escape') close() }

watch(() => props.modelValue, (open) => {
  if (open) {
    newName.value = ''
    load()
    nextTick(() => { if (!albums.value.length) nameInput.value?.focus() })
    window.addEventListener('keydown', onKey)
  } else {
    window.removeEventListener('keydown', onKey)
  }
}, { immediate: true })

onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>
