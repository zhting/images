<template>
  <div class="p-6">
    <h1 class="text-3xl font-bold mb-6 flex items-center gap-2">
      🌟 相似图优选 (Best Shots)
    </h1>
    
    <div v-if="loading" class="text-center py-20 text-gray-500">
        加载中...
    </div>
    
    <div v-if="!loading && groups.length === 0" class="text-center py-20 text-gray-500">
        太棒了！没有发现重复的连拍照片。
    </div>
    
    <div class="space-y-12">
        <div v-for="group in groups" :key="group.id" class="bg-white rounded-xl shadow-sm border p-6">
            <div class="flex justify-between items-center mb-4">
                <div class="text-gray-500 font-mono text-sm">
                    {{ formatTime(group.items[0].captured_time) }} · {{ group.items.length }} 张连拍
                </div>
                <!-- Optional: Group level actions -->
            </div>
            
            <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                <div v-for="(item, idx) in group.items" :key="item.file_path" class="relative group cursor-pointer">
                    <!-- Image -->
                    <div class="aspect-square rounded-lg overflow-hidden border-2 transition-all relative"
                         :class="item.is_best ? 'border-amber-400 ring-2 ring-amber-100' : 'border-transparent hover:ring-2 hover:ring-gray-200'"
                         @click="openGallery(group, idx)">
                         <img :src="`${API_BASE}/files/thumbnail?path=${encodeURIComponent(item.file_path)}`" class="w-full h-full object-cover">
                         
                         <!-- Aesthetic Score Badge -->
                         <div class="absolute bottom-1 right-1 bg-black/50 text-white text-[10px] px-1.5 py-0.5 rounded backdrop-blur-sm font-mono">
                             {{ Math.round(item.aesthetic_score * 100) }}%
                         </div>
                    </div>
                    
                    <!-- Best Badge -->
                    <div v-if="item.is_best" class="absolute -top-2 -right-2 bg-amber-400 text-white text-xs px-2 py-0.5 rounded-full shadow-lg z-10 font-bold flex items-center gap-1">
                        👑 推荐
                    </div>
                    
                    <!-- Selection Checkbox -->
                    <div class="absolute top-2 left-2 z-10" v-if="!item.is_best" @click.stop>
                        <input type="checkbox" v-model="item.selected" class="w-5 h-5 rounded border-gray-300 text-red-500 focus:ring-red-500">
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Load More Button -->
        <div v-if="hasMore" class="flex justify-center pt-8 pb-4">
            <button @click="loadMore" :disabled="loadingMore" class="px-6 py-2 bg-blue-500 hover:bg-blue-600 active:bg-blue-700 text-white rounded-full font-medium transition disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center gap-2">
                <span v-if="loadingMore">加载中...</span>
                <span v-else>加载更多</span>
            </button>
        </div>
        <div v-if="!hasMore && groups.length > 0 && !loading" class="text-center py-10 text-gray-400">
            已到达底部，没有更多连拍了
        </div>
    </div>
  </div>

  <!-- Gallery Modal -->
  <div v-if="gallery.open" class="fixed inset-0 z-50 bg-black/95 flex flex-col" @keydown.esc="closeGallery" tabindex="0">
      <!-- Toolbar -->
      <div class="flex justify-between items-center p-4 text-white bg-black/50 backdrop-blur-sm">
         <div class="flex items-center gap-4">
             <span>{{ gallery.currentIndex + 1 }} / {{ gallery.currentGroup.items.length }}</span>
             
             <!-- Set as Best Button -->
             <button v-if="!currentGalleryItem.is_best" 
                     @click="confirmSetBest"
                     class="bg-amber-500 hover:bg-amber-600 text-white text-sm px-4 py-1.5 rounded shadow transition-colors flex items-center gap-2">
                 <span>👑</span> 设为优选
             </button>
             <span v-else class="text-amber-400 font-bold flex items-center gap-2 bg-amber-900/30 px-3 py-1 rounded">
                 <span>👑</span> 当前优选
             </span>
         </div>
         <button @click="closeGallery" class="text-2xl font-bold p-2 hover:bg-white/20 rounded w-10 h-10 flex items-center justify-center">✕</button>
      </div>
      
      <!-- Main Image -->
      <div class="flex-1 flex items-center justify-center relative overflow-hidden" @click.self="closeGallery">
          <button @click="prevImage" class="absolute left-4 z-20 text-white text-4xl p-4 hover:bg-white/10 rounded-full transition-colors" v-if="gallery.currentIndex > 0">❮</button>
          
          <img :src="gallery.currentImage" class="max-h-full max-w-full object-contain select-none shadow-2xl" />
          
          <button @click="nextImage" class="absolute right-4 z-20 text-white text-4xl p-4 hover:bg-white/10 rounded-full transition-colors" v-if="gallery.currentIndex < gallery.currentGroup.items.length - 1">❯</button>
      </div>

      <!-- Thumbnails Strip -->
      <div class="h-24 bg-black/80 flex items-center gap-2 overflow-x-auto p-2" ref="thumbStrip">
          <div 
            v-for="(item, idx) in gallery.currentGroup.items" 
            :key="'thumb-'+idx"
            class="h-full aspect-square flex-shrink-0 cursor-pointer border-2 relative"
            :class="[
                idx === gallery.currentIndex ? 'border-white' : 'border-transparent opacity-50 hover:opacity-100',
                item.is_best ? 'ring-2 ring-amber-500 ring-offset-2 ring-offset-black' : ''
            ]"
            @click="setGalleryIndex(idx)"
            :id="'thumb-' + idx"
          >
              <img :src="`${API_BASE}/files/thumbnail?path=${encodeURIComponent(item.file_path)}`" class="h-full w-full object-cover" />
              <!-- Mini Best Badge -->
              <div v-if="item.is_best" class="absolute top-0 right-0 bg-amber-500 text-[8px] p-0.5 leading-none rounded-bl text-white">👑</div>
          </div>
      </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue'
import axios from 'axios'

const groups = ref([])
const loading = ref(true)
const loadingMore = ref(false)
const hasMore = ref(false)
const nextOffset = ref(0)
const API_BASE = 'http://localhost:8001'

// --- Gallery State ---
const gallery = ref({
    open: false,
    currentGroup: null, // Holds the group object
    currentIndex: 0,
    currentImage: ''
})
const thumbStrip = ref(null)

const currentGalleryItem = computed(() => {
    if (!gallery.value.currentGroup) return {}
    return gallery.value.currentGroup.items[gallery.value.currentIndex]
})

const formatTime = (ts) => {
    return new Date(ts * 1000).toLocaleString()
}

const setAsBest = (group, newItem) => {
    if (newItem.is_best) return
    
    // Find previous best and swap
    group.items.forEach(item => {
        if (item.is_best) {
            item.is_best = false
            item.selected = true // Mark old best for deletion
        }
    })
    
    newItem.is_best = true
    newItem.selected = false // Unmark new best
}

const confirmSetBest = () => {
    if (gallery.value.currentGroup && currentGalleryItem.value) {
        setAsBest(gallery.value.currentGroup, currentGalleryItem.value)
    }
}

const fetchBestShots = async (isLoadMore = false) => {
    if (isLoadMore) {
        loadingMore.value = true
    } else {
        loading.value = true
        groups.value = []
        nextOffset.value = 0
    }
    
    try {
        const res = await axios.get(`${API_BASE}/files/organize/best_shots`, {
            params: {
                limit: 15,
                offset_index: nextOffset.value
            }
        })
        
        const newGroups = res.data.groups.map(g => ({
            ...g,
            items: g.items.map(i => ({
                ...i,
                selected: !i.is_best // Default select non-best items
            }))
        }))
        
        if (isLoadMore) {
            groups.value = [...groups.value, ...newGroups]
        } else {
            groups.value = newGroups
        }
        
        hasMore.value = res.data.has_more
        nextOffset.value = res.data.next_offset
        
    } catch (e) {
        alert("Failed to load best shots: " + e.message)
    } finally {
        loading.value = false
        loadingMore.value = false
    }
}

const loadMore = () => {
    if (!loadingMore.value && hasMore.value) {
        fetchBestShots(true)
    }
}

// --- Gallery Logic ---
const openGallery = (group, index) => {
    gallery.value.currentGroup = group
    gallery.value.currentIndex = index
    updateImage()
    gallery.value.open = true
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', handleKey)
}

const closeGallery = () => {
    gallery.value.open = false
    document.body.style.overflow = ''
    window.removeEventListener('keydown', handleKey)
}

const updateImage = () => {
    const item = gallery.value.currentGroup.items[gallery.value.currentIndex]
    if(item) {
        // Use full content for main view (or high res thumbnail if preferred)
        gallery.value.currentImage = `${API_BASE}/files/content?path=${encodeURIComponent(item.file_path)}`
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
    if (gallery.value.currentIndex < gallery.value.currentGroup.items.length - 1) {
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
    fetchBestShots()
})
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
