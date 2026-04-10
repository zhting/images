<template>
  <div class="p-6">
    <h1 class="text-3xl font-bold mb-6 flex items-center gap-2">
      📄 文档归档 (Documents)
    </h1>
    
    <div v-if="loading" class="text-center py-20 text-gray-500">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto mb-4"></div>
        加载中...
    </div>
    
    <div v-else-if="docs.length === 0" class="text-center py-32">
        <div class="text-6xl mb-4 opacity-50">📄</div>
        <h3 class="text-xl font-medium text-gray-700 mb-2">暂无文档</h3>
        <p class="text-gray-500">目前您的图库中还没有被识别为文档的图片</p>
    </div>
    
    <div v-else>
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-6">
            <div v-for="doc in docs" :key="doc.file_path" class="group relative">
                <div class="aspect-[3/4] rounded-lg overflow-hidden border bg-gray-100 shadow-sm hover:shadow-md transition-all cursor-pointer">
                    <img :src="`${API_BASE}/files/thumbnail?path=${encodeURIComponent(doc.file_path)}`" class="w-full h-full object-contain p-2">
                </div>
                
                <div class="mt-2 flex items-start justify-between text-xs text-gray-500">
                    <span class="truncate pr-2">{{ doc.basename }}</span>
                    <span class="uppercase border px-1 rounded">{{ doc.tag }}</span>
                </div>
            </div>
        </div>

        <!-- Load More -->
        <div v-if="hasMore" class="mt-12 flex justify-center pb-20">
            <button 
                @click="fetchMore" 
                :disabled="loadingMore"
                class="px-8 py-3 bg-white hover:bg-gray-50 text-gray-700 rounded-lg text-sm font-semibold transition-all flex items-center gap-2 border shadow-sm disabled:opacity-50"
            >
                <span v-if="loadingMore" class="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></span>
                {{ loadingMore ? '加载中...' : '加载更多 (Load More)' }}
            </button>
        </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const docs = ref([])
const loading = ref(false)
const loadingMore = ref(false)
const hasMore = ref(true)
const currentPage = ref(1)
const pageSize = 30
const API_BASE = 'http://localhost:8001'

const fetchDocs = async (isLoadMore = false) => {
    if (isLoadMore) loadingMore.value = true
    else loading.value = true

    try {
        const pageToFetch = isLoadMore ? currentPage.value + 1 : 1
        const res = await axios.get(`${API_BASE}/files/organize/documents?page=${pageToFetch}&page_size=${pageSize}`)
        const data = res.data
        
        const newItems = data.items || (Array.isArray(data) ? data : [])
        
        if (isLoadMore) {
            docs.value = [...(docs.value || []), ...newItems]
            currentPage.value = pageToFetch
        } else {
            docs.value = newItems
            currentPage.value = 1
        }
        
        hasMore.value = docs.value.length < (data.total || docs.value.length)
    } catch (e) {
        alert("Failed to load documents: " + e.message)
    } finally {
        loading.value = false
        loadingMore.value = false
    }
}

const fetchMore = () => {
    if (!loadingMore.value && hasMore.value) {
        fetchDocs(true)
    }
}

onMounted(() => {
    fetchDocs()
})
</script>
