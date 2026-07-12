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

  <PhotoViewer
      v-if="gallery.open"
      :items="gallery.currentGroup.items"
      :start-index="gallery.currentIndex"
      :api-base="API_BASE"
      :allow-trash="false"
      @close="closeGallery"
      @index-change="i => gallery.currentIndex = i"
  >
      <template #toolbar>
          <button v-if="!currentGalleryItem.is_best"
                  @click="confirmSetBest"
                  class="bg-amber-500 hover:bg-amber-600 text-white text-sm px-4 py-1.5 rounded shadow transition-colors flex items-center gap-2">
              <span>👑</span> 设为优选
          </button>
          <span v-else class="text-amber-400 font-bold flex items-center gap-2 bg-amber-900/30 px-3 py-1 rounded">
              <span>👑</span> 当前优选
          </span>
      </template>
      <template #thumb-badge="{ item }">
          <div v-if="item.is_best" class="absolute top-0 right-0 bg-amber-500 text-[8px] p-0.5 leading-none rounded-bl text-white">👑</div>
      </template>
  </PhotoViewer>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import PhotoViewer from '../components/PhotoViewer.vue'
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
    gallery.value.open = true
}

const closeGallery = () => {
    gallery.value.open = false
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
