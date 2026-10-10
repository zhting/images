<template>
  <div class="p-4 sm:p-6 max-w-[1600px] mx-auto">
    <div v-if="loading" class="text-center py-24 text-gray-500 animate-pulse">正在整理回忆…</div>
    <div v-else-if="loadError" class="text-center py-24">
      <p class="text-gray-400 mb-4">回忆加载失败</p>
      <button @click="load" class="px-4 py-2 rounded-lg border border-line-strong text-gray-300 hover:bg-surface-hover">重试</button>
    </div>

    <EmptyState v-else-if="!data.years.length" :icon="Images" title="还没有回忆"
                description="索引带拍摄时间的照片后，这里会出现那年这周、旅行和年度回顾。" />

    <template v-else>
      <!-- This week in past years -->
      <section v-if="data.on_this_week.length" class="mb-10">
        <SectionHead title="那年这周">
          <router-link to="/on-this-day" class="text-sm text-blue-400 hover:text-blue-300">那年今日 ›</router-link>
        </SectionHead>
        <div class="flex gap-3 overflow-x-auto pb-2 -mx-1 px-1 snap-x">
          <button v-for="w in data.on_this_week" :key="w.year" @click="openWeek(w)"
                  class="relative shrink-0 w-64 sm:w-72 aspect-[4/3] rounded-xl overflow-hidden bg-surface-sunken snap-start group text-left">
            <img :src="thumb(w.cover, 'preview')" class="absolute inset-0 w-full h-full object-cover group-hover:scale-[1.03] transition-transform duration-500" loading="lazy" alt="" />
            <div class="absolute inset-0 bg-gradient-to-t from-black/75 via-black/10 to-transparent"></div>
            <div class="absolute bottom-0 inset-x-0 p-3 text-white">
              <div class="text-lg font-semibold">{{ w.years_ago }} 年前的这周</div>
              <div class="text-xs text-white/75">{{ shortRange(w.start, w.end - 1) }}，{{ w.year }} · {{ w.count }} 张</div>
            </div>
          </button>
        </div>
      </section>

      <!-- Trips -->
      <section class="mb-10">
        <SectionHead title="旅行" :count="data.trips.length" />
        <p v-if="!data.trips.length" class="text-sm text-gray-500">
          还没有识别出旅行。旅行根据照片的 GPS 位置和时间自动识别：离开常住地 60 公里以上、并拍了几张照片就算一次。
        </p>
        <div v-else class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          <router-link v-for="t in shownTrips" :key="t.id" :to="'/memories/trips/' + t.id"
                       class="group block rounded-xl overflow-hidden border border-line bg-surface-raised hover:border-line-stronger transition-colors">
            <div class="relative aspect-[16/9] bg-surface-sunken">
              <img :src="thumb(t.cover, 'preview')" class="absolute inset-0 w-full h-full object-cover" loading="lazy" alt="" />
              <div class="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent"></div>
              <svg v-if="t.path.length > 1" viewBox="0 0 100 60" class="absolute right-2 top-2 w-24 h-14 drop-shadow" aria-hidden="true">
                <polyline :points="miniRoute(t.path)" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="1 4" />
                <circle v-for="(pt, i) in miniPoints(t.path)" :key="i" :cx="pt[0]" :cy="pt[1]" r="2.6" :fill="i === 0 ? '#f59e0b' : 'white'" />
              </svg>
              <span v-if="t.abroad" class="absolute left-2 top-2 text-[11px] bg-black/50 text-white px-1.5 py-0.5 rounded">境外</span>
              <div class="absolute bottom-0 inset-x-0 p-3 text-white">
                <div class="text-lg font-semibold leading-tight truncate">{{ t.title }}</div>
                <div class="text-xs text-white/75 mt-0.5">{{ dateRange(t.start, t.end) }} · {{ t.days }} 天</div>
              </div>
            </div>
            <div class="px-3 py-2 flex items-center justify-between text-xs text-gray-400">
              <span class="truncate">{{ t.cities.slice(0, 4).join(' → ') }}</span>
              <span class="shrink-0 ml-2 flex items-center gap-1 text-blue-400 group-hover:text-blue-300">
                <Play :size="12" fill="currentColor" /> 回放
              </span>
            </div>
          </router-link>
        </div>
        <div v-if="data.trips.length > tripLimit" class="mt-4 text-center">
          <button @click="tripLimit += 12" class="text-sm text-blue-400 hover:text-blue-300">显示更多旅行（共 {{ data.trips.length }} 次）</button>
        </div>
      </section>

      <!-- Years -->
      <section class="mb-10">
        <SectionHead title="年度回顾" />
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          <router-link v-for="y in data.years" :key="y.year" :to="'/memories/year/' + y.year"
                       class="relative block aspect-[3/4] rounded-xl overflow-hidden bg-surface-sunken group">
            <img :src="thumb(y.cover, 'preview')" class="absolute inset-0 w-full h-full object-cover group-hover:scale-[1.03] transition-transform duration-500" loading="lazy" alt="" />
            <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-black/10 to-transparent"></div>
            <div class="absolute bottom-0 inset-x-0 p-3 text-white">
              <div class="text-3xl font-bold tracking-tight">{{ y.year }}</div>
              <div class="text-xs text-white/75 mt-0.5">{{ y.count.toLocaleString() }} 张<span v-if="y.trip_count"> · {{ y.trip_count }} 次旅行</span></div>
              <div v-if="y.places.length" class="text-xs text-white/60 truncate">{{ y.places.join(' · ') }}</div>
            </div>
          </router-link>
        </div>
      </section>
    </template>

    <PhotoViewer v-if="viewer.open" :items="viewerItems" :start-index="viewer.index"
                 @close="closeViewer" @trash="trashFromViewer" />
  </div>
</template>

<script setup>
/**
 * /memories — generated from metadata already in the library: this week
 * in earlier years, trips detected from GPS + time (each opens a route
 * playback), and a card per year.
 */
import { ref, computed, onMounted, h } from 'vue'
import axios from 'axios'
import { Images, Play } from 'lucide-vue-next'
import { API_BASE } from '../api/base'
import EmptyState from '../components/EmptyState.vue'
import PhotoViewer from '../components/PhotoViewer.vue'
import { usePhotoViewer } from '../composables/usePhotoViewer'

const data = ref({ on_this_week: [], trips: [], years: [] })
const loading = ref(true)
const loadError = ref(false)
const tripLimit = ref(9)
const viewerItems = ref([])
const { viewer, openViewer, closeViewer, trashFromViewer } = usePhotoViewer(viewerItems)

const shownTrips = computed(() => data.value.trips.slice(0, tripLimit.value))

const thumb = (p, size = 'grid') => `${API_BASE}/files/thumbnail?path=${encodeURIComponent(p)}&size=${size}`
const fmt = (ts, opts) => new Date(ts * 1000).toLocaleDateString('zh-CN', opts)
const shortRange = (a, b) => `${fmt(a, { month: 'numeric', day: 'numeric' })}–${fmt(b, { month: 'numeric', day: 'numeric' })}`
const dateRange = (a, b) => {
  const da = new Date(a * 1000), db = new Date(b * 1000)
  const start = fmt(a, { year: 'numeric', month: 'numeric', day: 'numeric' })
  if (da.toDateString() === db.toDateString()) return start
  return start + ' – ' + fmt(b, da.getFullYear() === db.getFullYear() ? { month: 'numeric', day: 'numeric' } : { year: 'numeric', month: 'numeric', day: 'numeric' })
}

// Tiny route sketch for trip cards: fit the stops into a 100x60 box.
const miniPoints = (path) => {
  const lats = path.map(p => p[0]), lons = path.map(p => p[1])
  const [la0, la1, lo0, lo1] = [Math.min(...lats), Math.max(...lats), Math.min(...lons), Math.max(...lons)]
  const k = Math.cos(((la0 + la1) / 2) * Math.PI / 180)   // degrees of longitude are shorter
  const s = Math.min(84 / Math.max((lo1 - lo0) * k, 1e-6), 44 / Math.max(la1 - la0, 1e-6))
  return path.map(([la, lo]) => [
    +(50 + (lo - (lo0 + lo1) / 2) * k * s).toFixed(1),
    +(30 - (la - (la0 + la1) / 2) * s).toFixed(1),
  ])
}
const miniRoute = (path) => miniPoints(path).map(p => p.join(',')).join(' ')

const openWeek = (w) => {
  viewerItems.value = w.photos
  openViewer(0)
}

const SectionHead = (props, { slots }) => h('div', { class: 'flex items-baseline justify-between mb-3' }, [
  h('h2', { class: 'text-lg font-semibold text-content' }, [
    props.title,
    props.count ? h('span', { class: 'ml-2 text-sm font-normal text-gray-500' }, `${props.count} 次`) : null,
  ]),
  slots.default?.(),
])
SectionHead.props = ['title', 'count']

const load = async () => {
  loading.value = true
  loadError.value = false
  try {
    const res = await axios.get(`${API_BASE}/memories`)
    data.value = res.data
  } catch (e) {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

onMounted(load)
defineExpose({ data, miniPoints })
</script>
