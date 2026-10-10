<template>
  <div class="p-4 sm:p-6 max-w-[1600px] mx-auto">
    <router-link to="/memories" class="inline-flex items-center gap-1 text-sm text-gray-400 hover:text-content mb-3">
      <ChevronLeft :size="16" /> 回忆
    </router-link>

    <div v-if="loading" class="text-center py-24 text-gray-500 animate-pulse">加载旅程…</div>
    <div v-else-if="error" class="text-center py-24 text-gray-400">
      {{ error }}
      <div class="mt-3"><router-link to="/memories" class="text-blue-400">返回回忆</router-link></div>
    </div>

    <template v-else-if="trip">
      <header class="mb-4">
        <h1 class="text-2xl sm:text-3xl font-semibold text-content">{{ trip.title }}</h1>
        <p class="text-sm text-gray-400 mt-1">
          {{ dateRange(trip.start, trip.end) }} · {{ trip.days }} 天 · {{ trip.stops.length }} 站 ·
          {{ trip.photo_count }} 张<span v-if="trip.distance_km"> · 约 {{ trip.distance_km.toLocaleString() }} 公里</span>
        </p>
      </header>

      <!-- Map + playback -->
      <div class="relative rounded-xl overflow-hidden border border-line bg-surface-sunken">
        <div ref="mapEl" class="w-full h-[52vh] sm:h-[60vh] min-h-[320px]"></div>

        <div v-if="tilesUnavailable"
             class="absolute top-3 left-14 right-3 lg:right-auto lg:max-w-sm z-[500] bg-surface-overlay/95 border border-line-strong rounded-lg px-3 py-2 text-xs text-gray-300">
          底图需要联网（OpenStreetMap），现在加载不了；路线和照片回放不受影响。
        </div>

        <!-- Current stop card (desktop: over the map) -->
        <div class="hidden lg:block absolute top-3 right-3 z-[500] w-80">
          <StopCard v-bind="cardProps" @open="openStopPhoto" @jump="scrollToStop" />
        </div>

        <!-- Controls -->
        <div class="absolute bottom-0 inset-x-0 z-[500] p-3 bg-gradient-to-t from-black/70 to-transparent">
          <div class="flex items-center gap-2 sm:gap-3">
            <button @click="togglePlay" class="w-10 h-10 shrink-0 rounded-full bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center shadow-lg"
                    :aria-label="playing ? '暂停' : '播放'">
              <Pause v-if="playing" :size="18" fill="currentColor" />
              <Play v-else :size="18" fill="currentColor" class="ml-0.5" />
            </button>
            <button @click="restart" class="w-8 h-8 shrink-0 rounded-full bg-black/40 hover:bg-black/60 text-white flex items-center justify-center" aria-label="从头播放">
              <RotateCcw :size="15" />
            </button>
            <div class="relative flex-1 h-6 cursor-pointer" ref="barEl" @click="onBarClick">
              <div class="absolute top-1/2 -translate-y-1/2 inset-x-0 h-1 rounded bg-white/25"></div>
              <div class="absolute top-1/2 -translate-y-1/2 left-0 h-1 rounded bg-blue-400" :style="{ width: (fraction * 100) + '%' }"></div>
              <button v-for="(s, i) in trip.stops" :key="i"
                      class="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3 h-3 rounded-full border-2 border-white/90"
                      :class="i <= cur.stop ? 'bg-blue-500' : 'bg-gray-700'"
                      :style="{ left: (stopStarts[i] * 100) + '%' }"
                      :title="s.name" :aria-label="'跳到 ' + s.name" @click.stop="seek(i)"></button>
            </div>
            <button @click="cycleSpeed" class="shrink-0 text-xs font-medium text-white bg-black/40 hover:bg-black/60 rounded-full px-2.5 py-1 tabular-nums" aria-label="播放速度">
              {{ speed }}×
            </button>
          </div>
        </div>

        <!-- First-run prompt -->
        <button v-if="!started" @click="togglePlay"
                class="absolute inset-0 z-[450] flex items-center justify-center bg-black/25 hover:bg-black/20 transition-colors group">
          <span class="flex items-center gap-2 bg-blue-600 group-hover:bg-blue-500 text-white rounded-full pl-4 pr-5 py-2.5 shadow-xl">
            <Play :size="18" fill="currentColor" /> 回放旅程
          </span>
        </button>
      </div>

      <!-- Current stop card (mobile: under the map) -->
      <div class="lg:hidden mt-3">
        <StopCard v-bind="cardProps" @open="openStopPhoto" @jump="scrollToStop" />
      </div>

      <!-- All photos, by stop -->
      <section class="mt-8">
        <div v-for="(s, i) in trip.stops" :key="i" :id="'stop-' + i" class="mb-6 scroll-mt-4">
          <h2 class="flex items-baseline gap-2 mb-2 text-sm">
            <span class="w-5 h-5 rounded-full bg-blue-600 text-white text-[11px] flex items-center justify-center shrink-0 self-center">{{ i + 1 }}</span>
            <span class="text-content font-medium">{{ s.name || '未知地点' }}</span>
            <span class="text-gray-500">第 {{ dayOf(s.arrive) }} 天 · {{ shortDate(s.arrive) }} · {{ byStop[i].length }} 张</span>
          </h2>
          <div class="grid grid-cols-3 sm:grid-cols-5 md:grid-cols-6 xl:grid-cols-8 gap-1">
            <button v-for="p in byStop[i]" :key="p.file_path" @click="openViewer(photos.indexOf(p))"
                    class="relative aspect-square bg-surface-sunken overflow-hidden">
              <img :src="thumb(p.file_path)" class="w-full h-full object-cover hover:opacity-90" loading="lazy" decoding="async" alt="" />
              <Play v-if="p.tag === 'video'" :size="16" class="absolute bottom-1 right-1 text-white drop-shadow" fill="currentColor" />
            </button>
          </div>
        </div>
      </section>

      <PhotoViewer v-if="viewer.open" :items="photos" :start-index="viewer.index"
                   @close="closeViewer" @trash="trashFromViewer" />
    </template>
  </div>
</template>

<script setup>
/**
 * /memories/trips/:id — one detected trip: the route on a map with a
 * playback that travels stop to stop and shows each stop's photos, then
 * every photo of the trip grouped by stop.
 */
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch, h } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { ChevronLeft, Play, Pause, RotateCcw, MapPin, Navigation } from 'lucide-vue-next'
import { API_BASE } from '../api/base'
import L from '../lib/leaflet'
import { createPlayback, distanceKm } from '../lib/routePlayback'
import PhotoViewer from '../components/PhotoViewer.vue'
import { usePhotoViewer } from '../composables/usePhotoViewer'

const route = useRoute()
const trip = ref(null)
const photos = ref([])
const loading = ref(true)
const error = ref('')
const mapEl = ref(null)
const barEl = ref(null)
const tilesUnavailable = ref(false)

const playing = ref(false)
const started = ref(false)
const speed = ref(1)
const fraction = ref(0)
const stopStarts = ref([])
const cur = ref({ stop: 0, phase: 'dwell', photoIndex: 0 })

const { viewer, openViewer, closeViewer, trashFromViewer } = usePhotoViewer(photos)

const thumb = (p, size = 'grid') => `${API_BASE}/files/thumbnail?path=${encodeURIComponent(p)}&size=${size}`
const fmt = (ts, opts) => new Date(ts * 1000).toLocaleDateString('zh-CN', opts)
const shortDate = (ts) => fmt(ts, { month: 'long', day: 'numeric' })
const dateRange = (a, b) => {
  const da = new Date(a * 1000), db = new Date(b * 1000)
  const start = fmt(a, { year: 'numeric', month: 'long', day: 'numeric' })
  if (da.toDateString() === db.toDateString()) return start
  return start + ' – ' + (da.getFullYear() === db.getFullYear() ? fmt(b, { month: 'long', day: 'numeric' }) : fmt(b, { year: 'numeric', month: 'long', day: 'numeric' }))
}
const dayOf = (ts) => {
  const d0 = new Date(trip.value.start * 1000); d0.setHours(0, 0, 0, 0)
  const d = new Date(ts * 1000); d.setHours(0, 0, 0, 0)
  return Math.round((d - d0) / 86400000) + 1
}

const byStop = computed(() => {
  const groups = (trip.value?.stops || []).map(() => [])
  for (const p of photos.value) groups[p.stop]?.push(p)
  return groups
})

// ---------------------------------------------------------------- stop card
const StopCard = (props, { emit }) => {
  const s = props.stop
  if (!s) return null
  const photo = s.highlights[props.photoIndex] || s.highlights[0]
  return h('div', { class: 'bg-surface-overlay/95 border border-line-strong rounded-xl shadow-2xl overflow-hidden' }, [
    photo
      ? h('button', { class: 'block w-full aspect-[4/3] bg-black', onClick: () => emit('open', photo), 'aria-label': '查看这张照片' },
          [h('img', { key: photo, src: thumb(photo, 'preview'), class: 'w-full h-full object-cover stop-photo', alt: '' })])
      : null,
    h('div', { class: 'px-3 py-2.5' }, [
      props.moving && props.next
        ? h('div', { class: 'flex items-center gap-1.5 text-sm text-blue-300' },
            [h(Navigation, { size: 14 }), `前往 ${props.next.name}`, h('span', { class: 'text-gray-500 ml-1' }, `${props.legKm} 公里`)])
        : h('div', { class: 'flex items-center gap-1.5 text-sm text-content font-medium' },
            [h(MapPin, { size: 14, class: 'text-blue-400' }), `${props.index + 1}. ${s.name || '未知地点'}`]),
      h('div', { class: 'flex items-center justify-between mt-0.5 text-xs text-gray-500' }, [
        h('span', `第 ${props.day} 天 · ${shortDate(s.arrive)}`),
        h('button', { class: 'text-blue-400 hover:text-blue-300', onClick: () => emit('jump', props.index) }, `本站 ${s.photo_count} 张 ›`),
      ]),
    ]),
  ])
}
StopCard.props = ['stop', 'next', 'index', 'photoIndex', 'moving', 'legKm', 'day']
StopCard.emits = ['open', 'jump']

const cardProps = computed(() => {
  const t = trip.value
  const i = cur.value.stop
  const s = t?.stops[i]
  const next = t?.stops[i + 1]
  return {
    stop: s, next, index: i, photoIndex: cur.value.photoIndex,
    moving: cur.value.phase === 'move',
    legKm: s && next ? Math.round(distanceKm([s.lat, s.lon], [next.lat, next.lon])) : 0,
    day: s ? dayOf(s.arrive) : 1,
  }
})

const openStopPhoto = (path) => {
  pause()
  const i = photos.value.findIndex(p => p.file_path === path)
  if (i !== -1) openViewer(i)
}
const scrollToStop = (i) => document.getElementById('stop-' + i)?.scrollIntoView({ behavior: 'smooth', block: 'start' })

// ---------------------------------------------------------------- map
let map = null
let runner = null
let trail = null
let stopMarkers = []
let pb = null
let raf = 0
let last = 0

const render = () => {
  const st = pb.state()
  fraction.value = st.fraction
  if (st.position) runner.setLatLng(st.position)
  trail.setLatLngs(st.trail)
  const c = cur.value
  if (c.stop !== st.stop || c.phase !== st.phase || c.photoIndex !== st.photoIndex) {
    cur.value = { stop: st.stop, phase: st.phase, photoIndex: st.photoIndex }
    stopMarkers.forEach((m, i) => m.getElement()?.classList.toggle('reached', i <= st.stop))
    preload(st.stop + 1)
  }
  if (st.done) pause()
}

const preloaded = new Set()
const preload = (i) => {
  const s = trip.value?.stops[i]
  if (!s || preloaded.has(i)) return
  preloaded.add(i)
  s.highlights.slice(0, 4).forEach(p => { const im = new Image(); im.src = thumb(p, 'preview') })
}

const frame = (ts) => {
  if (!playing.value) return
  const dt = last ? Math.min(ts - last, 100) : 16
  last = ts
  pb.advance(dt)
  render()
  if (playing.value) raf = requestAnimationFrame(frame)
}

const play = () => {
  if (!pb) return
  if (pb.done) pb.restart()
  started.value = true
  playing.value = true
  last = 0
  cancelAnimationFrame(raf)
  raf = requestAnimationFrame(frame)
}
const pause = () => { playing.value = false; cancelAnimationFrame(raf) }
const togglePlay = () => (playing.value ? pause() : play())
const restart = () => { pb?.restart(); render(); play() }
const seek = (i) => { pb?.seek(i); started.value = true; render() }
const cycleSpeed = () => {
  speed.value = speed.value === 1 ? 2 : speed.value === 2 ? 4 : 1
  pb?.setSpeed(speed.value)
}
const onBarClick = (e) => {
  const r = barEl.value.getBoundingClientRect()
  const f = (e.clientX - r.left) / r.width
  // jump to the last stop whose arrival is before the click
  let i = 0
  stopStarts.value.forEach((s, k) => { if (s <= f) i = k })
  seek(i)
}

const initMap = () => {
  const t = trip.value
  map = L.map(mapEl.value, { zoomControl: false, worldCopyJump: false })
  L.control.zoom({ position: 'topleft' }).addTo(map)
  let tileErrors = 0
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap', maxZoom: 18,
  })
    .on('tileerror', () => { if (++tileErrors >= 3) tilesUnavailable.value = true })
    .on('tileload', () => { tileErrors = 0; tilesUnavailable.value = false })
    .addTo(map)

  pb = createPlayback(t.stops, { dwellPhotos: (s) => s.highlights.length, speed: speed.value })
  stopStarts.value = pb.stopStarts

  L.polyline(pb.route, { color: '#93c5fd', weight: 2, opacity: 0.7, dashArray: '4 6' }).addTo(map)
  trail = L.polyline([], { color: '#3b82f6', weight: 4, opacity: 0.95 }).addTo(map)
  stopMarkers = t.stops.map((s, i) => L.marker([s.lat, s.lon], {
    icon: L.divIcon({ className: 'trip-stop', html: `<span>${i + 1}</span>`, iconSize: [22, 22] }),
    title: s.name,
    keyboard: false,
  }).on('click', () => seek(i)).addTo(map))
  runner = L.marker([t.stops[0].lat, t.stops[0].lon], {
    icon: L.divIcon({ className: 'trip-runner', html: '<span></span>', iconSize: [18, 18] }),
    interactive: false, zIndexOffset: 1000,
  }).addTo(map)

  if (pb.route.length > 1) map.fitBounds(L.latLngBounds(pb.route), { padding: [48, 48] })
  else map.setView([t.stops[0].lat, t.stops[0].lon], 12)
  render()
  preload(0)
}

const onKey = (e) => {
  if (viewer.open || !trip.value || e.target.closest?.('input,textarea')) return
  if (e.key === ' ') { e.preventDefault(); togglePlay() }
  else if (e.key === 'ArrowRight') seek(cur.value.stop + 1)
  else if (e.key === 'ArrowLeft') seek(cur.value.stop - 1)
}

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await axios.get(`${API_BASE}/trips/${encodeURIComponent(route.params.id)}`)
    trip.value = res.data
    photos.value = res.data.photos
  } catch (e) {
    error.value = e?.response?.status === 404 ? '找不到这次旅行，可能照片有变动，请回到回忆页重新进入' : '加载失败'
  } finally {
    loading.value = false
  }
  if (trip.value) {
    await nextTick()
    initMap()
  }
}

watch(viewer, (v) => { if (v.open) pause() })
onMounted(() => { load(); window.addEventListener('keydown', onKey) })
onBeforeUnmount(() => {
  pause()
  window.removeEventListener('keydown', onKey)
  map?.remove()
})
defineExpose({ trip, cur, seek, play, pause })
</script>

<style>
.trip-stop span {
  display: flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 9999px;
  background: #1f2937; color: #e5e7eb; font: 600 11px/1 system-ui, sans-serif;
  border: 2px solid #93c5fd; box-shadow: 0 1px 4px rgba(0,0,0,.5);
  transition: background .3s, border-color .3s;
}
.trip-stop.reached span { background: #2563eb; border-color: #fff; color: #fff; }
.trip-runner span {
  display: block; width: 18px; height: 18px; border-radius: 9999px;
  background: #f59e0b; border: 3px solid #fff; box-shadow: 0 0 0 6px rgba(245,158,11,.3);
}
.stop-photo { animation: stop-photo-in .45s ease; }
@keyframes stop-photo-in { from { opacity: 0; transform: scale(1.03); } to { opacity: 1; transform: none; } }
@media (prefers-reduced-motion: reduce) { .stop-photo { animation: none; } }
</style>
