<template>
  <div class="p-4 sm:p-6 max-w-[1600px] mx-auto">
    <router-link to="/memories" class="inline-flex items-center gap-1 text-sm text-gray-400 hover:text-content mb-3">
      <ChevronLeft :size="16" /> 回忆
    </router-link>

    <div v-if="loading" class="text-center py-24 text-gray-500 animate-pulse">加载中…</div>
    <div v-else-if="error" class="text-center py-24 text-gray-400">{{ error }}</div>

    <template v-else-if="y">
      <header class="flex flex-wrap items-end justify-between gap-3 mb-6">
        <div>
          <h1 class="text-4xl font-bold text-content tracking-tight">{{ y.year }}</h1>
          <p class="text-sm text-gray-400 mt-1">
            {{ y.count.toLocaleString() }} 张照片和视频<span v-if="y.videos"> · 其中视频 {{ y.videos }} 个</span>
            <span v-if="y.favorites"> · 收藏 {{ y.favorites }}</span>
            <span v-if="y.trips.length"> · {{ y.trips.length }} 次旅行</span>
          </p>
        </div>
        <router-link :to="{ path: '/search', query: { q: `${y.year}年` } }"
                     class="text-sm px-4 py-1.5 rounded-full border border-line-strong text-gray-300 hover:bg-surface-hover">
          查看这一年全部照片
        </router-link>
      </header>

      <!-- Month histogram -->
      <div class="flex items-end gap-1 sm:gap-2 h-24 mb-1" role="list" aria-label="每月照片数">
        <router-link v-for="(n, i) in y.months" :key="i" role="listitem"
                     :to="{ path: '/search', query: { q: `${y.year}年${i + 1}月` } }"
                     class="flex-1 flex flex-col justify-end h-full group" :title="`${i + 1}月：${n} 张`"
                     :class="n ? '' : 'pointer-events-none'">
          <div class="rounded-t bg-blue-500/70 group-hover:bg-blue-400 transition-colors"
               :style="{ height: n ? Math.max(4, n / maxMonth * 100) + '%' : '2px', opacity: n ? 1 : 0.25 }"></div>
        </router-link>
      </div>
      <div class="flex gap-1 sm:gap-2 text-[10px] text-gray-500 mb-6">
        <span v-for="i in 12" :key="i" class="flex-1 text-center">{{ i }}月</span>
      </div>

      <!-- Places & people -->
      <div v-if="y.places.length || y.people.length" class="flex flex-wrap gap-2 mb-6 text-sm">
        <router-link v-for="p in y.places" :key="'pl' + p.name"
                     :to="{ path: '/search', query: { q: `${y.year}年 ${p.name}` } }"
                     class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10">
          <MapPin :size="13" /> {{ p.name }} <span class="text-gray-500">{{ p.count }}</span>
        </router-link>
        <router-link v-for="p in y.people" :key="'pp' + p.person_id"
                     :to="{ path: '/search', query: { q: `${y.year}年 ${p.name}` } }"
                     class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full border border-violet-500/40 text-violet-300 hover:bg-violet-500/10">
          <User :size="13" /> {{ p.name }} <span class="text-gray-500">{{ p.count }}</span>
        </router-link>
      </div>

      <!-- Trips that year -->
      <div v-if="y.trips.length" class="flex gap-3 overflow-x-auto pb-2 mb-6">
        <router-link v-for="t in y.trips" :key="t.id" :to="'/memories/trips/' + t.id"
                     class="shrink-0 flex items-center gap-3 pr-4 rounded-xl border border-line bg-surface-raised hover:border-line-stronger">
          <img :src="thumb(t.cover)" class="w-16 h-16 object-cover rounded-l-xl" alt="" loading="lazy" />
          <div class="text-sm">
            <div class="text-content font-medium">{{ t.title }}</div>
            <div class="text-xs text-gray-500">{{ shortDate(t.start) }} · {{ t.days }} 天</div>
          </div>
        </router-link>
      </div>

      <!-- Highlights -->
      <h2 class="text-lg font-semibold text-content mb-3">精选</h2>
      <div class="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-1 [grid-auto-flow:dense]">
        <button v-for="(p, i) in highlights" :key="p.file_path" @click="openViewer(i)"
                class="relative bg-surface-sunken overflow-hidden"
                :class="i % 7 === 0 ? 'col-span-2 row-span-2' : ''">
          <div class="aspect-square">
            <img :src="thumb(p.file_path, i % 7 === 0 ? 'preview' : 'grid')" class="w-full h-full object-cover hover:opacity-90" loading="lazy" decoding="async" alt="" />
          </div>
          <Heart v-if="p.favorite" :size="14" class="absolute top-1.5 right-1.5 text-rose-400" fill="currentColor" />
          <Play v-if="p.tag === 'video'" :size="16" class="absolute bottom-1.5 right-1.5 text-white drop-shadow" fill="currentColor" />
        </button>
      </div>

      <PhotoViewer v-if="viewer.open" :items="highlights" :start-index="viewer.index"
                   @close="closeViewer" @trash="trashFromViewer" />
    </template>
  </div>
</template>

<script setup>
/** /memories/year/:year — a year at a glance: month histogram, places,
 *  people, trips and a spread of highlights. Everything links into the
 *  combined search for the full set. */
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { ChevronLeft, MapPin, User, Heart, Play } from 'lucide-vue-next'
import { API_BASE } from '../api/base'
import PhotoViewer from '../components/PhotoViewer.vue'
import { usePhotoViewer } from '../composables/usePhotoViewer'

const route = useRoute()
const y = ref(null)
const highlights = ref([])
const loading = ref(true)
const error = ref('')
const { viewer, openViewer, closeViewer, trashFromViewer } = usePhotoViewer(highlights)

const maxMonth = computed(() => Math.max(1, ...(y.value?.months || [1])))
const thumb = (p, size = 'grid') => `${API_BASE}/files/thumbnail?path=${encodeURIComponent(p)}&size=${size}`
const shortDate = (ts) => new Date(ts * 1000).toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' })

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await axios.get(`${API_BASE}/memories/year/${route.params.year}`)
    y.value = res.data
    highlights.value = res.data.highlights
  } catch (e) {
    error.value = e?.response?.status === 404 ? '这一年没有照片' : '加载失败'
  } finally {
    loading.value = false
  }
}
watch(() => route.params.year, (v) => { if (v) load() }, { immediate: true })
</script>
