<template>
  <div class="p-4 sm:p-6 max-w-[1600px] mx-auto pb-28">
    <header class="mb-4">
      <h1 class="text-2xl font-bold text-content flex items-center gap-2">
        <BrushCleaning :size="24" class="text-blue-500" /> 清理助手
      </h1>
      <p v-if="data" class="text-sm text-gray-400 mt-1">
        <template v-if="data.total_count">共 {{ data.total_count }} 项建议，可释放约 <b class="text-content">{{ fmtBytes(data.total_bytes) }}</b></template>
        <template v-else>没有需要清理的照片</template>
      </p>
      <p class="text-xs text-gray-500 mt-1">移入回收站的照片可以随时恢复；在回收站清空后才会真正释放空间。收藏的照片不会出现在建议里。</p>
      <p v-if="data?.quality?.pending" class="text-xs text-amber-300/80 mt-1">
        正在分析照片清晰度和曝光：还剩 {{ data.quality.pending }} 张，「模糊」「误拍」会陆续补全。
      </p>
      <p v-if="data?.hash_pending" class="text-xs text-amber-300/80 mt-1">
        正在为 {{ data.hash_pending }} 张旧照片计算文件指纹，完成后显示全部重复照片。
      </p>
    </header>

    <div v-if="loading && !data" class="text-center py-24 text-gray-500 animate-pulse">正在分析…</div>
    <div v-else-if="loadError" class="text-center py-24">
      <p class="text-gray-400 mb-4">加载失败</p>
      <button @click="load()" class="px-4 py-2 rounded-lg border border-line-strong text-gray-300 hover:bg-surface-hover">重试</button>
    </div>

    <template v-else-if="data">
      <!-- Categories -->
      <div class="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-2 sm:gap-3 mb-6" role="tablist">
        <button v-for="c in data.categories" :key="c.kind" role="tab" :aria-selected="tab === c.kind"
                @click="setTab(c.kind)"
                class="text-left rounded-xl border px-3 py-3 transition-colors"
                :class="tab === c.kind ? 'border-blue-500 bg-blue-500/10' : 'border-line bg-surface-raised hover:border-line-stronger'">
          <div class="flex items-center gap-2 text-sm" :class="c.count ? 'text-content' : 'text-gray-500'">
            <component :is="ICONS[c.kind]" :size="16" class="shrink-0" :class="c.count ? 'text-blue-400' : ''" />
            {{ c.label }}
          </div>
          <div class="mt-1.5 text-xl font-semibold tabular-nums" :class="c.count ? 'text-content' : 'text-gray-600'">{{ c.count }}</div>
          <div class="text-xs text-gray-500 tabular-nums">{{ c.count ? fmtBytes(c.bytes) : '—' }}</div>
        </button>
      </div>

      <section v-if="current">
        <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
          <p class="text-sm text-gray-400">{{ HELP[current.kind] }}</p>
          <div v-if="currentPaths.length" class="flex items-center gap-3 text-sm">
            <button class="text-blue-400 hover:text-blue-300" @click="selectAll(true)">全选</button>
            <button class="text-gray-400 hover:text-gray-300" @click="selectAll(false)">全不选</button>
          </div>
        </div>

        <div v-if="!current.count" class="text-center py-16 text-gray-500">
          <CircleCheck :size="36" class="mx-auto mb-2 text-emerald-500/70" />
          这一类没有需要清理的
        </div>

        <!-- Grouped: duplicates / bursts -->
        <div v-else-if="current.groups" class="space-y-3">
          <div v-for="(g, gi) in current.groups" :key="g.keep + gi"
               class="rounded-xl border border-line bg-surface-raised p-3">
            <div class="flex items-center justify-between text-xs text-gray-500 mb-2">
              <span>{{ current.kind === 'duplicates' ? `${g.items.length} 份相同文件` : `连拍 ${g.items.length} 张` }} · {{ fmtDate(g.items[0].captured_time) }}</span>
              <span v-if="g.items.every(it => selected.has(it.file_path))" class="text-red-400">整组都会被删除</span>
            </div>
            <div class="flex gap-2 overflow-x-auto pb-1">
              <Tile v-for="it in g.items" :key="it.file_path" :item="it" class="w-28 h-28 sm:w-32 sm:h-32 shrink-0"
                    :selected="selected.has(it.file_path)" :keeper="it.file_path === g.keep"
                    :label="current.kind === 'duplicates' ? folderOf(it.file_path) : sharpLabel(it)"
                    @toggle="toggle(it.file_path)" @open="open(g.items, it)" />
            </div>
          </div>
          <p v-if="current.truncated" class="text-xs text-gray-500 text-center">只显示前 {{ current.groups.length }} 组，清理后会显示更多</p>
        </div>

        <!-- Flat lists -->
        <div v-else>
          <div class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 xl:grid-cols-8 gap-2">
            <Tile v-for="it in current.items" :key="it.file_path" :item="it" class="aspect-square"
                  :selected="selected.has(it.file_path)" :label="itemLabel(it)"
                  @toggle="toggle(it.file_path)" @open="open(current.items, it)" />
          </div>
          <p v-if="current.truncated" class="mt-3 text-xs text-gray-500 text-center">只显示前 {{ current.items.length }} 项（共 {{ current.count }}），清理后会显示更多</p>
        </div>
      </section>
    </template>

    <!-- Action bar -->
    <div v-if="selectedInTab.length"
         class="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-2 sm:gap-4 whitespace-nowrap max-w-[calc(100vw-1.5rem)] bg-surface-overlay/95 border border-line-stronger rounded-xl shadow-2xl px-3 sm:px-5 py-3">
      <span class="text-sm text-gray-200">已选 {{ selectedInTab.length }} 项 · {{ fmtBytes(selectedBytes) }}</span>
      <button @click="trashSelected" :disabled="busy" class="bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white text-sm px-4 py-1.5 rounded-lg">移入回收站</button>
      <button @click="keepSelected" :disabled="busy" class="text-gray-300 hover:text-white text-sm" title="以后不再建议清理这些">不再建议</button>
    </div>

    <PhotoViewer v-if="viewer.open" :items="viewerItems" :start-index="viewer.index"
                 @close="closeViewer" @trash="trashFromViewer" />
  </div>
</template>

<script setup>
/**
 * /cleanup — suggestions of what to remove, by category, with the space
 * each would free. Duplicates/bursts/accidental shots come pre-selected
 * (a copy or the best shot is always kept); blurry photos, screenshots
 * and videos are left for the user to pick. Deleting = recycle bin, with
 * undo; "不再建议" hides items from that category for good.
 */
import { ref, computed, watch, onMounted, onBeforeUnmount, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { BrushCleaning, Copy, Layers, Moon, Focus, Smartphone, Video, CircleCheck, Check, Play } from 'lucide-vue-next'
import { API_BASE } from '../api/base'
import PhotoViewer from '../components/PhotoViewer.vue'
import { usePhotoViewer } from '../composables/usePhotoViewer'
import { toast } from '../composables/useToast'

const ICONS = { duplicates: Copy, bursts: Layers, accidental: Moon, blurry: Focus, screenshots: Smartphone, large_videos: Video }
const HELP = {
  duplicates: '内容完全相同的文件。每组保留收藏的或路径最短的那份，其余已预选。',
  bursts: '几秒内连拍的照片。每组保留最清晰（或已收藏）的一张，其余已预选。',
  accidental: '几乎全黑或一片空白的照片，多半是误触拍下的，已预选。',
  blurry: '对焦不准或手抖的照片，按模糊程度排序。请挑选后再删除。',
  screenshots: '一个月以前的截图，按时间从旧到新。',
  large_videos: '超过 100 MB 的视频，按大小排序。',
}

const route = useRoute()
const router = useRouter()
const data = ref(null)
const loading = ref(false)
const loadError = ref(false)
const busy = ref(false)
const tab = ref(route.query.tab || '')
const selected = ref(new Set())
const viewerItems = ref([])
const { viewer, openViewer, closeViewer, trashFromViewer } =
  usePhotoViewer(viewerItems, { onChange: () => { staleAfterViewer = true } })
let staleAfterViewer = false

const thumb = (p) => `${API_BASE}/files/thumbnail?path=${encodeURIComponent(p)}&size=grid`
const fmtBytes = (n) => {
  if (!n) return '0 B'
  const u = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.min(u.length - 1, Math.floor(Math.log(n) / Math.log(1024)))
  return `${(n / 1024 ** i).toFixed(i >= 2 ? 1 : 0)} ${u[i]}`
}
const fmtDate = (ts) => ts ? new Date(ts * 1000).toLocaleDateString('zh-CN', { year: 'numeric', month: 'numeric', day: 'numeric' }) : ''
const folderOf = (p) => p.replace(/\\/g, '/').split('/').slice(-2, -1)[0] || '/'
const sharpLabel = (it) => (it.sharpness != null && it.sharpness >= 0 ? `清晰度 ${Math.round(it.sharpness)}` : '')
const itemLabel = (it) => {
  const k = current.value?.kind
  if (k === 'blurry') return sharpLabel(it)
  if (k === 'accidental') return it.brightness != null && it.brightness < 22 ? '过暗' : '空白'
  if (k === 'screenshots') return it.text || fmtDate(it.captured_time)
  if (k === 'large_videos') return fmtBytes(it.size)
  return ''
}

const current = computed(() => data.value?.categories.find(c => c.kind === tab.value))
const itemsOf = (c) => c ? (c.groups ? c.groups.flatMap(g => g.items) : c.items) : []
const currentPaths = computed(() => itemsOf(current.value).map(it => it.file_path))
const selectedInTab = computed(() => currentPaths.value.filter(p => selected.value.has(p)))
const sizeOf = computed(() => {
  const m = new Map()
  for (const c of data.value?.categories || []) for (const it of itemsOf(c)) m.set(it.file_path, it.size || 0)
  return m
})
const selectedBytes = computed(() => selectedInTab.value.reduce((a, p) => a + (sizeOf.value.get(p) || 0), 0))

// --- tile ------------------------------------------------------------------
const Tile = (props, { emit }) => h('div', {
  class: ['relative group bg-surface-sunken rounded-lg overflow-hidden cursor-pointer',
    props.selected ? 'ring-2 ring-red-500' : props.keeper ? 'ring-2 ring-emerald-500/70' : ''],
  onClick: (e) => (e.ctrlKey || e.metaKey ? emit('toggle') : emit('open')),
}, [
  h('img', { src: thumb(props.item.file_path), class: ['w-full h-full object-cover', props.selected ? 'opacity-60' : ''], loading: 'lazy', decoding: 'async', alt: '' }),
  h('button', {
    class: ['absolute top-1 left-1 w-6 h-6 rounded-full flex items-center justify-center border',
      props.selected ? 'bg-red-600 border-red-600 text-white' : 'bg-black/50 border-white/60 text-transparent group-hover:text-white/70'],
    'aria-label': props.selected ? '取消选择' : '选择',
    'aria-pressed': String(!!props.selected),
    onClick: (e) => { e.stopPropagation(); emit('toggle') },
  }, [h(Check, { size: 14, 'stroke-width': 3 })]),
  props.keeper ? h('span', { class: 'absolute top-1 right-1 text-[10px] px-1.5 py-0.5 rounded bg-emerald-600 text-white' }, '保留') : null,
  props.item.tag === 'video' ? h(Play, { size: 16, class: 'absolute bottom-6 right-1 text-white drop-shadow', fill: 'currentColor' }) : null,
  props.label ? h('div', { class: 'absolute bottom-0 inset-x-0 px-1.5 py-0.5 text-[10px] text-white bg-black/60 truncate' }, props.label) : null,
])
Tile.props = ['item', 'selected', 'keeper', 'label']
Tile.emits = ['toggle', 'open']

// --- selection -----------------------------------------------------------------
const toggle = (p) => {
  const s = new Set(selected.value)
  s.has(p) ? s.delete(p) : s.add(p)
  selected.value = s
}
const selectAll = (on) => {
  const s = new Set(selected.value)
  const c = current.value
  // "全选" in a grouped category still leaves each group's keeper alone.
  const paths = c?.groups ? c.groups.flatMap(g => g.suggest) : currentPaths.value
  for (const p of (on ? paths : currentPaths.value)) on ? s.add(p) : s.delete(p)
  selected.value = s
}
const preselect = (d) => {
  const s = new Set()
  for (const c of d.categories) {
    if (!c.preselect) continue
    if (c.groups) c.groups.forEach(g => g.suggest.forEach(p => s.add(p)))
    else c.items.forEach(it => s.add(it.file_path))
  }
  return s
}

const setTab = (k) => {
  tab.value = k
  router.replace({ query: { ...route.query, tab: k } })
}

const open = (list, it) => {
  viewerItems.value = list.slice()
  openViewer(list.indexOf(it))
}
watch(() => viewer.open, (o) => { if (!o && staleAfterViewer) { staleAfterViewer = false; load(true) } })

// --- actions -----------------------------------------------------------------
const trashSelected = async () => {
  const paths = selectedInTab.value.slice()
  const bytes = selectedBytes.value
  busy.value = true
  try {
    await axios.post(`${API_BASE}/files/trash`, { file_paths: paths })
    const s = new Set(selected.value); paths.forEach(p => s.delete(p)); selected.value = s
    await load(true)
    toast(`已移入回收站 ${paths.length} 项（${fmtBytes(bytes)}）`, {
      actionLabel: '撤销', duration: 8000,
      onAction: async () => {
        try {
          await axios.post(`${API_BASE}/files/restore`, { file_paths: paths })
          await load(true)
        } catch (e) { toast('恢复失败', { type: 'error' }) }
      },
    })
  } catch (e) {
    toast('移入回收站失败', { type: 'error' })
  } finally {
    busy.value = false
  }
}

const keepSelected = async () => {
  const paths = selectedInTab.value.slice()
  busy.value = true
  try {
    await axios.post(`${API_BASE}/cleanup/keep`, { kind: tab.value, file_paths: paths })
    const s = new Set(selected.value); paths.forEach(p => s.delete(p)); selected.value = s
    await load(true)
    toast(`这 ${paths.length} 项以后不会再出现在「${current.value?.label || ''}」里`)
  } catch (e) {
    toast('操作失败', { type: 'error' })
  } finally {
    busy.value = false
  }
}

// --- loading -------------------------------------------------------------------
let poll = 0
const load = async (silent = false) => {
  if (!silent) { loading.value = true; loadError.value = false }
  try {
    const res = await axios.get(`${API_BASE}/cleanup`)
    const first = !data.value
    data.value = res.data
    if (first) {
      selected.value = preselect(res.data)
      if (!res.data.categories.some(c => c.kind === tab.value)) {
        tab.value = (res.data.categories.find(c => c.count) || res.data.categories[0]).kind
      }
    } else {
      // Keep the user's picks, drop ones that no longer exist.
      const alive = new Set(res.data.categories.flatMap(c => itemsOf(c).map(it => it.file_path)))
      selected.value = new Set([...selected.value].filter(p => alive.has(p)))
    }
    clearTimeout(poll)
    if (res.data.quality?.pending || res.data.hash_pending) poll = setTimeout(() => load(true), 15000)
  } catch (e) {
    if (!silent) loadError.value = true
  } finally {
    loading.value = false
  }
}

onMounted(() => load())
onBeforeUnmount(() => clearTimeout(poll))
defineExpose({ data, selected, tab })
</script>
