<template>
  <div class="h-full flex flex-col bg-gray-900">
    <!-- Header -->
    <div class="bg-gray-900 border-b border-gray-800 px-6 py-4 flex items-center justify-between shadow-sm z-10">
      <div class="flex items-center gap-4">
        <span class="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-indigo-400">
          📅 那年今日 (On This Day)
        </span>
        <span class="text-sm text-gray-400 bg-gray-800 px-2 py-1 rounded-full">
            {{ currentDate }}
        </span>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto scroll-smooth">
        <Transition name="fade" mode="out-in">
            <div v-if="loading" key="loading" class="space-y-10 pb-20 pt-6">
                <div v-for="i in 3" :key="i" class="space-y-4 px-6 animate-pulse">
                    <div class="flex items-center gap-4">
                        <div class="w-24 h-8 bg-gray-800 rounded"></div>
                        <div class="h-px bg-gray-800 flex-1"></div>
                        <div class="w-16 h-4 bg-gray-800 rounded"></div>
                    </div>
                    <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                        <div v-for="j in 6" :key="j" class="aspect-square bg-gray-800 rounded"></div>
                    </div>
                </div>
            </div>
            
            <div v-else-if="years.length === 0" key="empty" class="flex flex-col items-center justify-center h-full text-gray-400">
                <div class="text-6xl mb-4 text-gray-700">📅</div>
                <p class="text-lg font-medium">今天没有历史照片</p>
                <p class="text-sm opacity-50 mt-1 uppercase tracking-wider">No photos found for this date in previous years</p>
            </div>

            <div v-else key="content" class="space-y-10 pb-20 pt-6">
                <div v-for="group in years" :key="group.year" class="space-y-4">
                    <!-- Year Header -->
                    <div 
                        class="sticky top-0 z-10 bg-gray-900/95 backdrop-blur-sm py-2 px-6 flex items-center gap-4 cursor-pointer select-none hover:bg-gray-800/50 transition-colors"
                        @click="toggleYear(group.year)"
                    >
                        <span 
                            class="text-gray-400 text-xl transition-transform duration-300 transform"
                            :class="collapsedYears[group.year] ? '-rotate-90' : 'rotate-0'"
                        >
                            ▼
                        </span>
                        <h2 class="text-3xl font-black text-white tracking-tighter">{{ group.year }}</h2>
                        <div class="h-px bg-gray-800 flex-1"></div>
                        <span class="text-sm font-medium text-gray-500 bg-gray-800/50 px-2 py-0.5 rounded">{{ group.photos.length }} 张照片</span>
                    </div>
                    
                    <!-- Photos Grid -->
                    <div v-show="!collapsedYears[group.year]" class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 px-6">
                        <div v-for="(photo, index) in group.photos" :key="photo.file_path" class="aspect-square relative group cursor-pointer overflow-hidden rounded-lg bg-gray-800 ring-1 ring-white/5 shadow-lg" @click="openLightbox(photo, group.photos)">
                <img :src="`http://localhost:8001/files/thumbnail?path=${encodeURIComponent(photo.file_path)}`" class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110" loading="lazy" />
                <!-- Video Indicator -->
                <div v-if="photo.tag === 'video'" class="absolute top-2 right-2 z-10">
                    <div class="bg-black/40 rounded-full p-1.5 backdrop-blur-md ring-1 ring-white/20">
                        <svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                    </div>
                </div>
                <div class="absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
              </div>
                    </div>
                </div>
            </div>
        </Transition>
    </div>
    <PhotoViewer
        v-if="lightbox.open"
        :items="lightbox.photos"
        :start-index="lightbox.currentIndex"
        :api-base="API_BASE"
        :allow-trash="false"
        @close="closeLightbox"
        @index-change="i => lightbox.currentIndex = i"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import PhotoViewer from '../components/PhotoViewer.vue'

const API_BASE = 'http://localhost:8001'
import { searchState } from '../store'

const years = computed(() => searchState.onThisDayData)
const loading = ref(!searchState.onThisDayLoaded)
const collapsedYears = ref({})

const toggleYear = (year) => {
    collapsedYears.value[year] = !collapsedYears.value[year]
}

    const lightbox = ref({
      open: false,
      currentPhoto: null,
      currentIndex: 0,
      photos: []
    })

const currentDate = computed(() => {
    const d = new Date()
    return `${d.getMonth() + 1}月${d.getDate()}日`
})

const fetchData = async () => {
    if (searchState.onThisDayLoaded) {
        loading.value = false
        return
    }
    
    loading.value = true
    try {
        const res = await fetch('http://localhost:8001/files/organize/on_this_day')
        searchState.onThisDayData = await res.json()
        searchState.onThisDayLoaded = true
    } catch (e) {
        console.error(e)
    } finally {
        loading.value = false
    }
}

// Gallery Logic
const openLightbox = (photo, groupPhotos) => {
    const idx = groupPhotos.findIndex(p => p.file_path === photo.file_path)
    if (idx === -1) return
    lightbox.value.photos = groupPhotos
    lightbox.value.currentIndex = idx
    lightbox.value.open = true
}

const closeLightbox = () => {
    lightbox.value.open = false
}

onMounted(() => {
    fetchData()
})
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.4s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

div::-webkit-scrollbar {
  width: 8px;
  height: 8px;
  background-color: transparent;
}
div::-webkit-scrollbar-thumb {
  background-color: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
}
div::-webkit-scrollbar-thumb:hover {
  background-color: rgba(255, 255, 255, 0.2);
}
</style>
