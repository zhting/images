<template>
    <!-- Top Bar -->
    <TopBar />

    <div class="px-4 pb-20 pt-6"> <!-- content wrapper -->
        
        <!-- Loading State -->
        <div v-if="loading || searchState.loading" class="text-center py-10">
            <span class="animate-pulse text-xl">Loading...</span>
        </div>

        <!-- 1. Timeline View -->
        <div v-else-if="searchState.mode === 'timeline'" class="timeline-container relative">
            <!-- Vertical Line (Visible now, z-0) -->
            <div class="absolute left-4 md:left-[8.5rem] top-0 bottom-0 w-0.5 bg-blue-100 z-0"></div>

            <div v-for="(group, key) in groups" :key="key" class="mb-8 flex flex-col md:flex-row gap-4 relative z-10">
                 <!-- Date Label (Left sticky) -->
                <div class="md:w-32 flex-shrink-0 text-right pr-4 hidden md:block pt-1">
                     <div class="sticky top-24 transition-all">
                        <span class="font-bold text-gray-700 text-lg">{{ key }}</span>
                        <div class="text-xs text-gray-400 mt-0.5">{{ group.length }} 张</div>
                     </div>
                </div>
                <!-- Mobile Date Label -->
                <div class="pl-8 md:hidden mb-2">
                     <span class="font-bold text-gray-800">{{ key }}</span> <span class="text-xs text-gray-500">({{ group.length }})</span>
                </div>
                
                <!-- Timeline Dot (Hollow style, z-10) -->
                <div class="absolute left-4 md:left-[8.5rem] top-2.5 w-3 h-3 bg-white rounded-full border-[3px] border-blue-500 shadow-sm -translate-x-1/2"></div>

                <!-- Grid -->
                <div class="flex-1">
                    <div class="month-grid grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
                        <div v-for="(item, index) in group" :key="item.file_path" class="relative group cursor-pointer aspect-square overflow-hidden rounded bg-gray-100" @click="openGallery(group, index)">
                            <img :src="getThumbUrl(item.file_path)" class="w-full h-full object-cover hover:scale-105 transition-transform duration-300" loading="lazy" />
                            <!-- Burst Badge -->
                             <div v-if="item.similar_count > 0" class="absolute top-1 right-1 bg-black/60 text-white text-[10px] px-1.5 rounded-full backdrop-blur-sm border border-white/20">
                                 +{{ item.similar_count }}
                             </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 2. Search View -->
        <div v-else-if="searchState.mode === 'search'" class="search-container">
            <div class="mb-4 flex items-center justify-between">
                <h3 class="text-xl font-bold flex items-baseline gap-2">
                    搜索: "{{ searchState.query }}"
                    <span v-if="searchState.translatedQuery" class="text-gray-500 text-sm font-normal">
                        ({{ searchState.translatedQuery }})
                    </span>
                </h3>
                <span class="text-gray-500">
                    {{ searchState.results.length }} 个结果
                    <span v-if="searchState.duration" class="ml-2 text-sm bg-gray-100 px-2 py-0.5 rounded">
                        耗时 {{ searchState.duration }}s
                    </span>
                </span>
            </div>

            <div v-if="searchState.results.length === 0" class="text-center py-20 text-gray-500">
                <div class="text-4xl mb-4">🤔</div>
                没有找到相关照片
            </div>
            
            <div class="month-grid grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2">
                <div v-for="(item, index) in searchState.results" :key="item.file_path" class="relative group cursor-pointer" @click="openGallery(searchState.results, index)">
                    <img :src="getThumbUrl(item.file_path)" class="w-full h-40 object-cover rounded shadow-sm hover:opacity-90 transition-none" loading="lazy" />
                    <div class="absolute bottom-0 left-0 right-0 bg-black/50 text-white text-xs p-1 truncate">
                        <div class="flex justify-between items-center">
                            <span class="truncate pr-2 flex-1">{{ item.basename }}</span>
                            <span class="opacity-90 flex-shrink-0 bg-black/30 px-1 rounded">相似度 {{ (item.score * 100).toFixed(2) }}%</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
    </div>

    <!-- Gallery Modal -->
    <div v-if="gallery.open" class="fixed inset-0 z-50 bg-black/95 flex flex-col" @keydown.esc="closeGallery" tabindex="0">
        <!-- Toolbar -->
        <div class="flex justify-between items-center p-4 text-white bg-black/50">
           <span>{{ gallery.currentIndex + 1 }} / {{ gallery.currentItems.length }}</span>
           <button @click="closeGallery" class="text-2xl font-bold p-2 hover:bg-white/20 rounded">✕</button>
        </div>
        
        <!-- Main Image -->
        <div class="flex-1 flex items-center justify-center relative overflow-hidden">
            <button @click="prevImage" class="absolute left-4 z-20 text-white text-4xl p-4 hover:bg-white/10 rounded-full" v-if="gallery.currentIndex > 0">❮</button>
            <img :src="gallery.currentImage" class="max-h-full max-w-full object-contain select-none" />
            <button @click="nextImage" class="absolute right-4 z-20 text-white text-4xl p-4 hover:bg-white/10 rounded-full" v-if="gallery.currentIndex < gallery.currentItems.length - 1">❯</button>
        </div>

        <!-- Thumbnails Strip -->
        <div class="h-24 bg-black/80 flex items-center gap-2 overflow-x-auto p-2" ref="thumbStrip">
            <div 
              v-for="(item, idx) in gallery.currentItems" 
              :key="'thumb-'+idx"
              class="h-full aspect-square flex-shrink-0 cursor-pointer border-2"
              :class="idx === gallery.currentIndex ? 'border-red-500' : 'border-transparent opacity-60 hover:opacity-100'"
              @click="setGalleryIndex(idx)"
              :id="'thumb-' + idx"
            >
                <img :src="getThumbUrl(item.file_path)" class="h-full w-full object-cover" />
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue'
import axios from 'axios'
import TopBar from './TopBar.vue'
import { searchState } from '../store'

const items = ref([])
const loading = ref(true)
const API_BASE = 'http://localhost:8000'

const gallery = ref({
    open: false,
    currentItems: [], // Flat list of items in the current context (e.g. Month or Search Results)
    currentIndex: 0,
    currentImage: ''
})

// Fetch Timeline
onMounted(async () => {
    try {
        const res = await axios.get(`${API_BASE}/timeline`)
        items.value = res.data
    } catch (e) {
        console.error(e)
    } finally {
        loading.value = false
    }
})

// Group by Month (computed)
const groups = computed(() => {
    // Only group if in timeline mode
    if (searchState.mode !== 'timeline') return {}
    
    const g = {}
    items.value.forEach(item => {
        const dt = new Date(item.captured_time * 1000)
        const key = isNaN(dt.getTime()) ? 'Unknown' : `${dt.getFullYear()}-${String(dt.getMonth()+1).padStart(2, '0')}`
        if (!g[key]) g[key] = []
        g[key].push(item)
    })
    return g
})

const getFileUrl = (path) => {
    return `${API_BASE}/files/content?path=${encodeURIComponent(path)}`
}

const getThumbUrl = (path) => {
    return `${API_BASE}/files/thumbnail?path=${encodeURIComponent(path)}`
}

// Gallery Logic
const openGallery = (sourceItems, index) => {
    gallery.value.currentItems = sourceItems
    gallery.value.currentIndex = index
    gallery.value.currentImage = getFileUrl(sourceItems[index].file_path)
    gallery.value.open = true
    
    window.addEventListener('keydown', handleKey)
}

const closeGallery = () => {
    gallery.value.open = false
    window.removeEventListener('keydown', handleKey)
}

const updateImage = () => {
    const item = gallery.value.currentItems[gallery.value.currentIndex]
    if(item) {
        gallery.value.currentImage = getFileUrl(item.file_path)
        scrollToThumb()
    }
}

const prevImage = () => {
    if (gallery.value.currentIndex > 0) {
        gallery.value.currentIndex--
        updateImage()
    }
}

const nextImage = () => {
    if (gallery.value.currentIndex < gallery.value.currentItems.length - 1) {
        gallery.value.currentIndex++
        updateImage()
    }
}

const setGalleryIndex = (idx) => {
    gallery.value.currentIndex = idx
    updateImage()
}

const handleKey = (e) => {
    if (e.key === 'ArrowLeft') prevImage()
    if (e.key === 'ArrowRight') nextImage()
    if (e.key === 'Escape') closeGallery()
}

// Auto scroll thumbnails
const thumbStrip = ref(null)
const scrollToThumb = () => {
    nextTick(() => {
        const el = document.getElementById('thumb-' + gallery.value.currentIndex)
        if (el && thumbStrip.value) {
            el.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
        }
    })
}

</script>

<style scoped>
/* Hidden Scrollbar for cleaner look */
div::-webkit-scrollbar {
  height: 8px;
  background-color: #000;
}
div::-webkit-scrollbar-thumb {
  background-color: #333;
  border-radius: 4px;
}
</style>
