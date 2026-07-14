<template>
  <div class="p-8 max-w-[1600px] mx-auto">
    <div class="flex justify-between items-end mb-8 border-b border-line pb-4">
      <h1 class="text-3xl font-light text-white flex items-center gap-3">
        回收站
        <span class="text-base text-gray-600 font-mono mt-1">{{ items.length }} 项</span>
      </h1>
      <div class="flex gap-3" v-if="items.length > 0">
        <button v-if="selectedItems.size > 0" @click="restoreSelected" class="px-5 py-1.5 bg-line text-green-500 hover:bg-line-strong hover:text-green-400 rounded text-sm transition-colors border border-line-strong">
          还原 ({{ selectedItems.size }})
        </button>
        <button v-if="selectedItems.size > 0" @click="deleteSelected" class="px-5 py-1.5 bg-[#311] text-red-500 hover:bg-[#411] hover:text-red-400 rounded text-sm transition-colors border border-[#422]">
          永久删除 ({{ selectedItems.size }})
        </button>
        <button @click="toggleSelectAll" class="px-5 py-1.5 bg-transparent text-gray-500 hover:text-gray-300 rounded text-sm transition-colors border border-line-strong hover:border-[#555]">
          {{ selectedItems.size === items.length ? '取消全选' : '全选' }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="text-center py-32 text-gray-700 text-sm tracking-widest uppercase">加载中...</div>

    <div v-else-if="items.length === 0" class="text-center py-32 text-gray-800">
      <div class="text-6xl mb-4 opacity-20">🗑️</div>
      <div class="text-gray-600">回收站是空的</div>
    </div>

    <div v-else class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8 gap-1">
      <div 
        v-for="(item, idx) in items" 
        :key="item.file_path" 
        class="relative group aspect-square bg-surface-sunken cursor-pointer"
        @click="openGallery(items, idx)"
      >
        <!-- Overlay for selection state -->
        <div class="absolute inset-0 bg-blue-500/20 z-10 border-2 border-blue-500 pointer-events-none" v-if="selectedItems.has(item.file_path)"></div>

        <img :src="getThumbUrl(item.file_path)" class="w-full h-full object-cover transition-opacity duration-300 hover:opacity-100" :class="selectedItems.has(item.file_path) ? 'opacity-100' : 'opacity-70'" />
        
        <div class="absolute top-2 right-2 rounded-full w-5 h-5 flex items-center justify-center bg-black/40 border border-white/30 hover:bg-blue-500 hover:border-blue-500 transition-colors z-20"
             :class="selectedItems.has(item.file_path) ? '!bg-blue-500 !border-blue-500' : ''"
             @click.stop="toggleSelect(item.file_path)">
             <span v-if="selectedItems.has(item.file_path)" class="text-white text-xs font-bold">✓</span>
        </div>
        
        <!-- Hover Date info -->
        <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent pt-6 pb-1 px-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <div class="text-white/80 text-[10px] font-mono truncate">{{ formatTime(item.captured_time) }}</div>
        </div>
      </div>
    </div>
  </div>

  <!-- Gallery Modal -->
  <div v-if="gallery.open" class="fixed inset-0 z-50 bg-black/95 flex flex-col" @keydown.esc="closeGallery" tabindex="0">
      <!-- Toolbar -->
      <div class="flex justify-between items-center p-4 text-white bg-black/50 backdrop-blur-sm z-30 absolute top-0 left-0 right-0">
          <span class="font-mono">{{ gallery.currentIndex + 1 }} / {{ gallery.currentItems.length }}</span>
          
          <div class="flex items-center gap-4">
              <button @click="closeGallery" class="text-2xl font-bold p-2 hover:bg-white/20 rounded w-10 h-10 flex items-center justify-center">✕</button>
          </div>
      </div>
      
      <!-- Main Image/Video -->
      <div class="flex-1 flex items-center justify-center relative overflow-hidden" @click.self="closeGallery">
          <button @click="prevImage" class="absolute left-4 z-20 text-white text-4xl p-4 hover:bg-white/10 rounded-full" v-if="gallery.currentIndex > 0">❮</button>
          
          <img :src="gallery.currentImage" class="max-h-full max-w-full object-contain select-none shadow-2xl" />
          
          <button @click="nextImage" class="absolute right-4 z-20 text-white text-4xl p-4 hover:bg-white/10 rounded-full" v-if="gallery.currentIndex < gallery.currentItems.length - 1">❯</button>
      </div>

      <!-- Thumbnails Strip -->
      <div class="h-24 bg-black/80 flex items-center gap-2 overflow-x-auto p-2" ref="thumbStrip">
          <div 
            v-for="(item, idx) in gallery.currentItems" 
            :key="'thumb-'+idx"
            class="h-full aspect-square flex-shrink-0 cursor-pointer border-2"
            :class="idx === gallery.currentIndex ? 'border-blue-500' : 'border-transparent opacity-60 hover:opacity-100'"
            @click="setGalleryIndex(idx)"
            :id="'thumb-' + idx"
          >
              <img :src="getThumbUrl(item.file_path)" class="h-full w-full object-cover" />
          </div>
      </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'

const items = ref([])
const loading = ref(true)
const selectedItems = ref(new Set())
const API_BASE = 'http://localhost:8001'

const loadTrash = async () => {
    loading.value = true
    try {
        const res = await axios.get(`${API_BASE}/files/organize/trash`)
        items.value = res.data
        selectedItems.value.clear()
    } catch (e) {
        console.error(e)
    } finally {
        loading.value = false
    }
}

const getThumbUrl = (path) => {
    return `${API_BASE}/files/thumbnail?path=${encodeURIComponent(path)}`
}

const getFileUrl = (path) => {
    return `${API_BASE}/files/content?path=${encodeURIComponent(path)}`
}

const formatTime = (ts) => {
    if (!ts) return ''
    return new Date(ts * 1000).toLocaleDateString()
}

const toggleSelect = (path) => {
    if (selectedItems.value.has(path)) {
        selectedItems.value.delete(path)
    } else {
        selectedItems.value.add(path)
    }
}

const toggleSelectAll = () => {
    if (selectedItems.value.size === items.value.length) {
        selectedItems.value.clear()
    } else {
        items.value.forEach(i => selectedItems.value.add(i.file_path))
    }
}

const restoreSelected = async () => {
    if (!confirm(`确定要还原这 ${selectedItems.value.size} 个文件吗？`)) return
    
    try {
        await axios.post(`${API_BASE}/files/restore`, {
            file_paths: Array.from(selectedItems.value)
        })
        await loadTrash()
    } catch (e) {
        alert("还原失败: " + e)
    }
}

const deleteSelected = async () => {
    if (!confirm(`⚠️ 警告：这将永久删除这 ${selectedItems.value.size} 个文件，无法恢复！确定吗？`)) return
    
    try {
        // DELETE with body is not standard in axios alias, use request
        await axios.delete(`${API_BASE}/files/trash`, {
            data: { file_paths: Array.from(selectedItems.value) }
        })
        await loadTrash()
    } catch (e) {
        alert("删除失败: " + e)
    }
}

// --- Gallery Logic ---
const gallery = ref({
    open: false,
    currentItems: [], 
    currentIndex: 0,
    currentImage: ''
})

const openGallery = (sourceItems, index) => {
    gallery.value.currentItems = sourceItems
    gallery.value.currentIndex = index
    
    // Pre-calculate image to avoid flash
    const item = sourceItems[index]
    if(item) gallery.value.currentImage = getFileUrl(item.file_path)
    
    gallery.value.open = true
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', handleKey)
    scrollToThumb('auto') // Initial scroll
}

const closeGallery = () => {
    gallery.value.open = false
    document.body.style.overflow = ''
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
const scrollToThumb = (behavior = 'smooth') => {
    nextTick(() => {
        attemptScroll(behavior)
        setTimeout(() => attemptScroll(behavior), 100)
    })
}

const attemptScroll = (behavior) => {
    const el = document.getElementById('thumb-' + gallery.value.currentIndex)
    if (el && thumbStrip.value) {
        el.scrollIntoView({ behavior: behavior, block: 'nearest', inline: 'center' })
    }
}

import { watch } from 'vue'
watch(() => gallery.value.open, (val) => {
    if (val) {
        scrollToThumb('auto')
    }
})

import { nextTick } from 'vue'
onMounted(loadTrash)

</script>
