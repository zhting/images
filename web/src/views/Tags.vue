<template>
  <div class="h-full flex flex-col bg-gray-900">
    <!-- Header -->
    <div class="bg-gray-900 border-b border-gray-800 px-6 py-4 flex items-center justify-between shadow-sm z-10">
      <div class="flex items-center gap-4">
        <button v-if="selectedTag" @click="selectedTag = null" class="text-gray-300 hover:text-white transition-colors">
           ← 返回
        </button>
        <span class="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-pink-400 to-rose-400">
          {{ selectedTag ? (selectedTag.display_name || selectedTag.name) : '标签 (Tags)' }}
        </span>
         <span v-if="selectedTag" class="text-sm text-gray-400 bg-gray-800 px-2 py-1 rounded-full">
            {{ photos.length }} photos
        </span>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto p-6 scroll-smooth">
        <Transition name="fade" mode="out-in">
            <!-- Loading Skeleton -->
            <div v-if="loading && !selectedTag" key="loading" class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4 animate-pulse">
                <div v-for="i in 16" :key="i" class="bg-gray-800/50 rounded-2xl p-6 min-h-[120px] shadow-sm ring-1 ring-white/5"></div>
            </div>

            <!-- Detail View Skeleton -->
            <div v-else-if="loading && selectedTag" key="loading-detail" class="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2 animate-pulse">
                <div v-for="i in 12" :key="i" class="aspect-square bg-gray-800 rounded-lg"></div>
            </div>

            <!-- Tags Cloud / Grid -->
            <div v-else-if="!selectedTag" key="tags-grid">
                <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4 pb-10">
                    <div 
                        v-for="tag in tags" 
                        :key="tag.name"
                        class="group relative bg-gray-800/40 rounded-2xl p-6 shadow-sm ring-1 ring-white/5 border border-transparent hover:shadow-lg hover:-translate-y-1 hover:border-pink-500/30 hover:bg-gray-800/60 cursor-pointer transition-all duration-300 flex flex-col items-center justify-center min-h-[120px]"
                        @click="selectTag(tag)"
                    >
                        <!-- Badge -->
                        <span class="absolute top-3 right-3 bg-gray-900 text-gray-400 text-[10px] font-mono px-1.5 py-0.5 rounded-full group-hover:bg-pink-500 group-hover:text-white transition-colors">
                            {{ tag.count }}
                        </span>

                        <!-- Main Text -->
                        <span class="text-gray-200 font-bold text-lg mb-1 group-hover:text-pink-400 transition-colors text-center tracking-tight">
                            {{ tag.display_name || tag.name }}
                        </span>
                        
                        <!-- Sub Text (English) -->
                        <span v-if="tag.display_name && tag.display_name !== tag.name" class="text-[10px] text-gray-500 font-medium uppercase tracking-[0.2em] opacity-60 group-hover:opacity-100 transition-opacity">
                            {{ tag.name }}
                        </span>
                    </div>
                </div>

                <!-- Pagination -->
                <div v-if="totalPages > 1" class="mt-8 flex flex-col items-center gap-4 pb-16">
                    <div class="flex items-center gap-2">
                        <!-- Prev -->
                        <button 
                            @click="goToPage(currentPage - 1)" 
                            :disabled="currentPage === 1"
                            class="p-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-30 disabled:hover:bg-gray-800 text-gray-300 rounded-lg transition-colors border border-gray-700"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                                <path fill-rule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clip-rule="evenodd" />
                            </svg>
                        </button>

                        <!-- Pages -->
                        <div class="flex items-center gap-1.5">
                            <button 
                                v-for="p in visiblePages" 
                                :key="p"
                                @click="goToPage(p)"
                                :class="[
                                    'min-w-[40px] h-10 flex items-center justify-center rounded-lg text-sm font-medium transition-all border',
                                    p === currentPage 
                                        ? 'bg-rose-600 border-rose-500 text-white shadow-lg shadow-rose-900/20' 
                                        : p === '...' 
                                            ? 'border-transparent text-gray-600 cursor-default' 
                                            : 'bg-gray-800 border-gray-700 text-gray-400 hover:bg-gray-700 hover:text-white'
                                ]"
                            >
                                {{ p }}
                            </button>
                        </div>

                        <!-- Next -->
                        <button 
                            @click="goToPage(currentPage + 1)" 
                            :disabled="currentPage === totalPages"
                            class="p-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-30 disabled:hover:bg-gray-800 text-gray-300 rounded-lg transition-colors border border-gray-700"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                                <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
                            </svg>
                        </button>
                    </div>
                    <div class="text-xs text-gray-500 font-medium">
                        第 {{ currentPage }} 页 / 共 {{ totalPages }} 页 ({{ totalCount }} 个标签)
                    </div>
                </div>
            </div>

            <!-- Detail View -->
            <div v-else key="detail-view" class="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
                <div 
                    v-for="photo in photos" 
                    :key="photo.file_path"
                    class="relative group aspect-square bg-gray-800 rounded-lg overflow-hidden cursor-pointer"
                >
                     <img 
                        loading="lazy"
                        :src="`http://localhost:8001/files/thumbnail?path=${encodeURIComponent(photo.file_path)}`" 
                        class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" 
                    />
                </div>
            </div>
        </Transition>
        
         <!-- Empty -->
        <div v-if="!loading && !selectedTag && tags.length === 0" class="flex flex-col items-center justify-center h-full text-gray-500">
             <div class="text-5xl mb-4 text-gray-700 opacity-20">🏷️</div>
             <p class="font-medium">暂无标签</p>
        </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue'
import { searchState } from '../store'

const tags = computed(() => searchState.tagsData || [])
const selectedTag = ref(null)
const photos = ref([])
const loading = ref(false)

const currentPage = ref(1)
const totalCount = ref(0)
const pageSize = 80 // Increased for better tag cloud overview
const API_BASE = 'http://localhost:8001'

const totalPages = computed(() => Math.ceil(totalCount.value / pageSize))

const visiblePages = computed(() => {
    const total = totalPages.value
    const current = currentPage.value
    const delta = 2
    const range = []
    
    for (let i = Math.max(2, current - delta); i <= Math.min(total - 1, current + delta); i++) {
        range.push(i)
    }
    
    if (current - delta > 2) range.unshift('...')
    range.unshift(1)
    
    if (current + delta < total - 1) range.push('...')
    if (total > 1) range.push(total)
    
    return range
})

const fetchTags = async (targetPage = 1) => {
    console.log('[fetchTags] Start', targetPage)
    loading.value = true

    try {
        console.log('[fetchTags] Fetching from API...')
        const res = await fetch(`${API_BASE}/files/organize/tags?page=${targetPage}&page_size=${pageSize}`)
        console.log('[fetchTags] Fetch completed, status:', res.status)
        const data = await res.json()
        console.log('[fetchTags] JSON parsed:', data)
        
        const newItems = data.items || (Array.isArray(data) ? data : [])
        console.log('[fetchTags] Extracted items:', newItems.length)
        
        searchState.tagsData = newItems
        currentPage.value = targetPage
        totalCount.value = data.total || searchState.tagsData.length
        searchState.tagsLoaded = true

        // Scroll to top
        nextTick(() => {
            const container = document.querySelector('.overflow-y-auto')
            if (container) container.scrollTop = 0
            console.log('[fetchTags] nextTick executed')
        })
    } catch (e) {
        console.error('[fetchTags] Error:', e)
    } finally {
        loading.value = false
        console.log('[fetchTags] Loading set to false')
    }
}

const goToPage = (p) => {
    if (p === '...' || p === currentPage.value) return
    fetchTags(p)
}

const selectTag = async (tag) => {
    selectedTag.value = tag
    loading.value = true
    try {
        const res = await fetch(`${API_BASE}/files/organize/tags/${encodeURIComponent(tag.name)}`)
        const data = await res.json()
        photos.value = Array.isArray(data) ? data : []
    } catch (e) {
        console.error(e)
        photos.value = []
    } finally {
        loading.value = false
    }
}

onMounted(() => {
    fetchTags()
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
