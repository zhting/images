<template>
  <div class="h-full flex flex-col bg-gray-50">
    <!-- Header -->
    <div class="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between shadow-sm z-10">
      <div class="flex items-center gap-4">
        <span class="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-500 to-indigo-600">
          📅 那年今日 (On This Day)
        </span>
        <span class="text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
            {{ currentDate }}
        </span>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto p-6 scroll-smooth">
        <div v-if="loading" class="flex justify-center py-20">
             <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
        </div>
        
        <div v-else-if="years.length === 0" class="flex flex-col items-center justify-center h-full text-gray-400">
             <div class="text-6xl mb-4">📅</div>
             <p class="text-lg">今天没有历史照片</p>
             <p class="text-xs mt-2">No photos found for this date in previous years.</p>
        </div>

        <div v-else class="space-y-10 pb-20">
            <div v-for="group in years" :key="group.year" class="space-y-4">
                <!-- Year Header -->
                <div class="flex items-center gap-4">
                    <h2 class="text-3xl font-black text-gray-800">{{ group.year }}</h2>
                    <div class="h-px bg-gray-200 flex-1"></div>
                    <span class="text-sm text-gray-400">{{ group.photos.length }} photos</span>
                </div>
                
                <!-- Photos Grid -->
                <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                    <div 
                        v-for="(photo, idx) in group.photos" 
                        :key="photo.file_path"
                        class="relative group aspect-square bg-gray-200 rounded-xl overflow-hidden cursor-pointer shadow-sm hover:shadow-lg transition-all"
                        @click="openLightbox(photo, group.photos)"
                    >
                         <img 
                            loading="lazy"
                            :src="`http://localhost:8000/files/thumbnail?path=${encodeURIComponent(photo.file_path)}`" 
                            class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110" 
                        />
                        <div class="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors"></div>
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
                <img :src="`http://localhost:8000/files/thumbnail?path=${encodeURIComponent(item.file_path)}`" class="h-full w-full object-cover" />
            </div>
        </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue'

const years = ref([])
const loading = ref(true)

const gallery = ref({
    open: false,
    currentItems: [], 
    currentIndex: 0,
    currentImage: ''
})

const thumbStrip = ref(null)

const currentDate = computed(() => {
    const d = new Date()
    return `${d.getMonth() + 1}月${d.getDate()}日`
})

const fetchData = async () => {
    loading.value = true
    try {
        const res = await fetch('http://localhost:8000/files/organize/on_this_day')
        years.value = await res.json()
    } catch (e) {
        console.error(e)
    } finally {
        loading.value = false
    }
}

// Gallery Logic
const openLightbox = (photo, groupPhotos) => {
    // Find index in the group
    const idx = groupPhotos.findIndex(p => p.file_path === photo.file_path)
    if (idx === -1) return

    gallery.value.currentItems = groupPhotos
    gallery.value.currentIndex = idx
    updateImage()
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
        gallery.value.currentImage = `http://localhost:8000/files/content?path=${encodeURIComponent(item.file_path)}`
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

const scrollToThumb = () => {
    nextTick(() => {
        const el = document.getElementById('thumb-' + gallery.value.currentIndex)
        if (el && thumbStrip.value) {
            el.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
        }
    })
}

onMounted(() => {
    fetchData()
})
</script>

<style scoped>
div::-webkit-scrollbar {
  height: 8px;
  background-color: #000;
}
div::-webkit-scrollbar-thumb {
  background-color: #333;
  border-radius: 4px;
}
</style>
