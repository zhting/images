<template>
  <div class="p-4 sm:p-6 max-w-[1600px] mx-auto">
    <!-- Search box -->
    <form class="flex gap-2 mb-3" @submit.prevent="submit">
      <div class="relative flex-1">
        <Search :size="16" class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
        <input ref="input" v-model="draft" type="search" enterkeyhint="search"
               placeholder="试试：去年夏天在大理和妈妈的合照、&quot;发票&quot;、2024年 截图"
               class="w-full bg-surface-sunken border border-line-strong rounded-full py-2.5 pl-9 pr-4 text-content placeholder-gray-600 outline-none focus:border-blue-500" />
      </div>
      <button type="submit" class="hidden sm:block bg-blue-600 hover:bg-blue-500 text-white rounded-full px-6 text-sm">搜索</button>
    </form>

    <!-- Interpreted filters -->
    <div v-if="parsed && (parsed.chips.length || parsed.text)" class="flex flex-wrap items-center gap-2 mb-3 text-sm">
      <span class="text-gray-500">已识别：</span>
      <span v-for="c in parsed.chips" :key="c.kind + c.token"
            class="inline-flex items-center gap-1 pl-2.5 pr-1 py-0.5 rounded-full border"
            :class="CHIP_STYLES[c.kind] || 'border-line-strong text-gray-300'">
        <component :is="CHIP_ICONS[c.kind]" :size="13" class="opacity-80" />
        {{ c.label }}
        <button @click="removeChip(c)" class="p-0.5 rounded-full hover:bg-white/10" :aria-label="'去掉 ' + c.label"><X :size="12" /></button>
      </span>
      <span v-if="parsed.text" class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full border border-line-strong text-gray-300">
        <Sparkles :size="13" class="opacity-80" /> 画面：{{ parsed.text }}
        <span v-if="translated" class="text-gray-500">（{{ translated }}）</span>
      </span>
    </div>

    <!-- Status line -->
    <div class="flex flex-wrap items-center justify-between gap-2 mb-4 text-sm text-gray-500 min-h-[1.5rem]">
      <span v-if="loading">搜索中…</span>
      <span v-else-if="query">
        {{ results.length }} 个结果<span v-if="results.length >= TOP_K">（只显示最相关的 {{ TOP_K }} 个）</span>
        <span v-if="elapsed" class="ml-2 text-gray-600">{{ elapsed }}s</span>
      </span>
      <span class="flex items-center gap-3">
        <span v-if="ocrNote" class="text-xs text-gray-500">{{ ocrNote }}</span>
        <SlideshowButton v-if="!loading && results.some(r => r.tag !== 'video')" :source="'search:' + query" :title="query" />
      </span>
    </div>

    <!-- Empty / error / idle -->
    <div v-if="error" class="text-center py-16 text-gray-400">
      搜索失败：{{ error }} <button class="ml-2 text-blue-400" @click="run">重试</button>
    </div>
    <div v-else-if="!query" class="py-12 text-sm text-gray-500 max-w-xl mx-auto leading-7">
      <p class="text-gray-300 mb-2">一个搜索框，可以组合这些条件：</p>
      <ul class="list-disc pl-5">
        <li>画面内容：<button class="text-blue-400" @click="tryQuery('海边的日落')">海边的日落</button>、<button class="text-blue-400" @click="tryQuery('猫在沙发上')">猫在沙发上</button></li>
        <li>时间：今年、去年夏天、2024年3月、上个月、最近7天</li>
        <li>地点和人物：照片里出现过的城市、你在「人物」里起过名字的人</li>
        <li>照片里的文字：加引号，如 <button class="text-blue-400" @click="tryQuery('&quot;发票&quot;')">"发票"</button>；不加引号也会同时匹配文字</li>
        <li>类型：视频、截图、文档、收藏</li>
      </ul>
    </div>
    <div v-else-if="!loading && results.length === 0" class="text-center py-16 text-gray-500">
      <div class="text-gray-400 mb-1">没有找到符合条件的照片</div>
      <div v-if="parsed && parsed.chips.length" class="text-sm">可以去掉上面的某个条件再试试</div>
    </div>

    <!-- Results -->
    <div v-if="results.length" class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8 gap-1">
      <div v-for="(item, idx) in results" :key="item.file_path"
           class="relative group cursor-pointer aspect-square bg-surface-sunken overflow-hidden"
           @click="onClick($event, idx)">
        <img :src="thumbUrl(item.file_path)" class="w-full h-full object-cover" loading="lazy" decoding="async"
             :class="selected.has(item.file_path) ? 'ring-2 ring-inset ring-blue-500 opacity-80 scale-[0.93]' : ''" />
        <button class="absolute top-1 left-1 w-5 h-5 rounded-full flex items-center justify-center z-10 transition-opacity"
                :class="[selected.has(item.file_path) ? 'bg-blue-600 text-white' : 'bg-black/50 text-white/80',
                         (selected.size || selected.has(item.file_path)) ? 'opacity-100' : 'opacity-0 group-hover:opacity-100']"
                @click.stop="toggle(item)" :aria-label="selected.has(item.file_path) ? '取消选择' : '选择'">
          <Check :size="12" :stroke-width="3" />
        </button>
        <div v-if="item.tag === 'video'" class="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div class="bg-black/30 rounded-full p-1.5"><Play :size="16" class="text-white" fill="currentColor" /></div>
        </div>
        <div class="absolute bottom-0 inset-x-0 p-1 flex items-end gap-1 pointer-events-none">
          <span v-if="item.match.includes('text')" class="bg-amber-500/90 text-black text-[10px] px-1 rounded" :title="item.snippet">文字</span>
          <span v-if="item.snippet" class="text-[10px] text-white bg-black/60 px-1 rounded truncate">{{ item.snippet }}</span>
        </div>
      </div>
    </div>

    <!-- Selection bar -->
    <div v-if="selected.size > 0"
         class="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-2 sm:gap-4 whitespace-nowrap max-w-[calc(100vw-1.5rem)] bg-surface-overlay/95 border border-line-stronger rounded-xl shadow-2xl px-3 sm:px-5 py-3">
      <span class="text-sm text-gray-200">已选 {{ selected.size }} 张</span>
      <button @click="showPicker = true" class="bg-blue-600 hover:bg-blue-500 text-white text-sm px-4 py-1.5 rounded-lg">加入相册</button>
      <button @click="trashSelected" class="bg-red-600 hover:bg-red-500 text-white text-sm px-4 py-1.5 rounded-lg">移入回收站</button>
      <button @click="selected = new Set()" class="text-gray-400 hover:text-gray-200 text-sm">取消</button>
    </div>

    <AlbumPicker v-model="showPicker" :count="selected.size" @pick="addToAlbum" />
    <PhotoViewer v-if="viewer.open" :items="results" :start-index="viewer.index"
                 @close="closeViewer" @trash="trashFromViewer" />
  </div>
</template>

<script setup>
/**
 * /search?q=… — the combined search page. The query lives in the URL, so
 * back/forward, reload and bookmarks work, and the search box elsewhere
 * just navigates here. The backend (/search/smart) turns time/place/
 * person/type phrases into filters, matches text found in photos, and
 * ranks the rest with the existing image vectors.
 */
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { Search, X, Sparkles, Clock, MapPin, User, Type, Film, Heart, Check, Play } from 'lucide-vue-next'
import { API_BASE } from '../api/base'
import PhotoViewer from '../components/PhotoViewer.vue'
import AlbumPicker from '../components/AlbumPicker.vue'
import SlideshowButton from '../components/SlideshowButton.vue'
import { usePhotoViewer } from '../composables/usePhotoViewer'
import { toast } from '../composables/useToast'

const TOP_K = 200
const CHIP_ICONS = { time: Clock, place: MapPin, person: User, text: Type, type: Film, favorite: Heart }
const CHIP_STYLES = {
  time: 'border-sky-500/40 text-sky-300', place: 'border-emerald-500/40 text-emerald-300',
  person: 'border-violet-500/40 text-violet-300', text: 'border-amber-500/40 text-amber-300',
  type: 'border-line-strong text-gray-300', favorite: 'border-rose-500/40 text-rose-300',
}

const route = useRoute()
const router = useRouter()
const input = ref(null)
const draft = ref('')
const query = ref('')
const results = ref([])
const parsed = ref(null)
const translated = ref(null)
const ocr = ref(null)
const loading = ref(false)
const error = ref('')
const elapsed = ref('')
const selected = ref(new Set())
const showPicker = ref(false)

const { viewer, openViewer, closeViewer, trashFromViewer } = usePhotoViewer(results)

const thumbUrl = (p) => `${API_BASE}/files/thumbnail?path=${encodeURIComponent(p)}&size=grid`

const ocrNote = computed(() => {
  const o = ocr.value
  if (!o) return ''
  if (!o.available) return '未安装文字识别组件，照片里的文字暂不能搜索'
  if (o.state === 'disabled') return '照片文字识别已在设置中关闭'
  if (o.pending > 0) return `照片文字识别进行中：已完成 ${o.done}，还剩 ${o.pending}，文字搜索结果会逐渐完整`
  return ''
})

let seq = 0
const run = async () => {
  const q = query.value
  error.value = ''
  if (!q.trim()) { results.value = []; parsed.value = null; return }
  const mine = ++seq
  loading.value = true
  const t0 = performance.now()
  try {
    const res = await axios.get(`${API_BASE}/search/smart`, { params: { q, top_k: TOP_K } })
    if (mine !== seq) return       // a newer search superseded this one
    results.value = res.data.results
    parsed.value = res.data.parsed
    translated.value = res.data.translated_query
    ocr.value = res.data.ocr
    elapsed.value = ((performance.now() - t0) / 1000).toFixed(2)
    selected.value = new Set()
  } catch (e) {
    if (mine === seq) error.value = e?.response?.data?.detail || e.message || '网络错误'
  } finally {
    if (mine === seq) loading.value = false
  }
}

const submit = () => {
  const q = draft.value.trim()
  if (q === (route.query.q || '')) run()
  else router.push({ path: '/search', query: q ? { q } : {} })
}
const tryQuery = (q) => { draft.value = q; submit() }

// Removing a chip deletes the words it was read from.
const removeChip = (chip) => {
  draft.value = query.value.replace(chip.token, ' ').replace(/\s+/g, ' ').trim()
  submit()
}

const toggle = (item) => {
  const next = new Set(selected.value)
  next.has(item.file_path) ? next.delete(item.file_path) : next.add(item.file_path)
  selected.value = next
}
const onClick = (e, idx) => {
  if (e.ctrlKey || e.metaKey || selected.value.size) toggle(results.value[idx])
  else openViewer(idx)
}

const addToAlbum = async (album) => {
  const paths = [...selected.value]
  try {
    const res = await axios.post(`${API_BASE}/albums/${album.id}/items`, { file_paths: paths })
    toast(`已加入「${album.name}」${res.data.added} 张`)
    selected.value = new Set()
  } catch (e) {
    toast('加入相册失败', { type: 'error' })
  }
}

const trashSelected = async () => {
  const paths = [...selected.value]
  const snapshot = results.value.slice()
  results.value = results.value.filter(r => !selected.value.has(r.file_path))
  selected.value = new Set()
  try {
    await axios.post(`${API_BASE}/files/trash`, { file_paths: paths })
    toast(`已移入回收站 ${paths.length} 张`, {
      actionLabel: '撤销', duration: 8000,
      onAction: async () => {
        try {
          await axios.post(`${API_BASE}/files/restore`, { file_paths: paths })
          results.value = snapshot
        } catch (e) { toast('恢复失败', { type: 'error' }) }
      },
    })
  } catch (e) {
    results.value = snapshot
    toast('移入回收站失败', { type: 'error' })
  }
}

watch(() => route.query.q, (q) => {
  query.value = q || ''
  draft.value = q || ''
  run()
}, { immediate: true })

onMounted(() => { if (!query.value) input.value?.focus() })
defineExpose({ results, parsed })
</script>
