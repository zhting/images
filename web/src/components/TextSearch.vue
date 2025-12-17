<template>
  <div class="max-w-6xl mx-auto">
    <div class="bg-white rounded-lg shadow p-6 mb-8">
      <h2 class="text-2xl font-bold mb-4 flex items-center gap-2">
        <span>🔍</span> 文本检索
      </h2>
      
      <div class="flex gap-4">
        <input 
          v-model="query" 
          @keyup.enter="handleSearch"
          type="text" 
          placeholder="描述图片内容 (例如: 'Running dog' or '在海边玩耍的孩子')" 
          class="flex-1 border border-gray-300 rounded px-4 py-2 focus:outline-none focus:ring-2 focus:ring-red-500"
        >
        <button 
          @click="handleSearch" 
          class="bg-red-500 text-white px-6 py-2 rounded font-semibold hover:bg-red-600 transition-colors disabled:opacity-50"
          :disabled="loading || !query"
        >
          {{ loading ? '搜索中...' : '搜索' }}
        </button>
      </div>
      
      <div class="mt-4 flex items-center gap-4">
          <label class="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
              <input type="checkbox" v-model="useTranslation" class="rounded text-red-500 focus:ring-red-500">
              启用中英翻译 (Deep Translator)
          </label>
          <div class="text-sm text-gray-500 ml-auto">
             Top K: 
             <select v-model.number="topK" class="border rounded px-2 py-1">
                 <option>10</option>
                 <option>20</option>
                 <option>50</option>
             </select>
          </div>
      </div>
    </div>

    <!-- Results -->
    <div v-if="results.length > 0" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
       <div v-for="(item, idx) in results" :key="idx" class="group relative bg-white rounded-lg shadow overflow-hidden hover:shadow-lg transition-shadow">
          <div class="aspect-square bg-gray-100 relative overflow-hidden">
              <img :src="getFileUrl(item.file_path)" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" loading="lazy">
          </div>
          <div class="p-2 text-sm flex justify-between items-center bg-white border-t">
              <span class="truncate font-mono text-gray-700" :title="item.basename">{{ item.basename }}</span>
              <span class="text-xs bg-gray-100 text-gray-500 px-1 rounded">{{ item.score.toFixed(3) }}</span>
          </div>
       </div>
    </div>
    
    <div v-if="hasSearched && results.length === 0 && !loading" class="text-center text-gray-500 py-10">
        未找到相关图片
    </div>

  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

const query = ref('')
const loading = ref(false)
const results = ref([])
const useTranslation = ref(true)
const topK = ref(20)
const hasSearched = ref(false)

const getFileUrl = (path) => {
    return `${API_BASE}/files/content?path=${encodeURIComponent(path)}`
}

const handleSearch = async () => {
    if (!query.value) return
    loading.value = true
    hasSearched.value = true
    results.value = []
    
    try {
        const res = await axios.post(`${API_BASE}/search/text`, {
            query: query.value,
            top_k: topK.value,
            use_translation: useTranslation.value
        })
        results.value = res.data
    } catch (e) {
        console.error(e)
        alert('搜索失败: ' + (e.response?.data?.detail || e.message))
    } finally {
        loading.value = false
    }
}
</script>
