<template>
  <div class="sticky top-0 z-40 bg-[#0f0f0f]/90 backdrop-blur border-b border-[#222] flex items-center justify-between px-6 h-16 gap-4">
      
      <!-- Left: Tabs (Pill Switch) -->
      <div class="flex-shrink-0 bg-[#222] p-1 rounded-lg">
          <button 
            v-for="t in ['text', 'image', 'ai']" 
            :key="t"
            @click="currentTab = t; resetTimeline()"
            class="px-4 py-1.5 rounded-md text-sm font-normal transition-all"
            :class="currentTab === t ? 'bg-[#333] text-white shadow-sm' : 'text-gray-500 hover:text-gray-300'"
          >
            {{ t === 'text' ? '文本' : (t === 'image' ? '图片' : 'AI') }}
          </button>
      </div>

      <!-- Right: Content Area (Expands) -->
      <div class="flex-1 max-w-3xl flex justify-end items-center">
          
          <!-- Text Search Mode -->
          <div v-if="currentTab === 'text'" class="w-full flex gap-2">
              <div class="relative flex-1">
                  <input 
                    v-model="query" 
                    @keydown.enter="doTextSearch"
                    @blur="onBlur(); showHistory = false" @focus="showHistory = true"
                    type="text" 
                    placeholder="搜索你的回忆..." 
                    class="w-full border border-[#333] rounded-full py-2 px-4 pl-10 focus:outline-none focus:border-blue-500 bg-[#1a1a1a] text-white placeholder-gray-600 transition-colors"
                  >
                  <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">🔍</span>
                  <!-- Search history -->
                  <div v-if="showHistory && history.length"
                       class="absolute top-full left-0 right-0 mt-2 bg-[#1f1f1f] border border-[#333] rounded-xl shadow-2xl z-50 overflow-hidden">
                      <div v-for="h in history" :key="h"
                           class="px-4 py-2 text-sm text-gray-300 hover:bg-[#2a2a2a] cursor-pointer flex justify-between items-center group"
                           @mousedown.prevent="searchFromHistory(h)">
                          <span class="truncate">{{ h }}</span>
                          <button class="text-gray-600 hover:text-gray-300 opacity-0 group-hover:opacity-100 px-1"
                                  @mousedown.prevent.stop="removeHistory(h)">✕</button>
                      </div>
                      <div class="px-4 py-1.5 text-xs text-gray-600 border-t border-[#2a2a2a] flex justify-between">
                          <span>最近搜索</span>
                          <button class="hover:text-gray-400" @mousedown.prevent="clearHistory">清空</button>
                      </div>
                  </div>
                  <button 
                    v-if="query" 
                    @click="resetTimeline"
                    class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 p-1 rounded-full hover:bg-[#333] transition-colors"
                  >
                    ✕
                  </button>
              </div>
              <button @click="doTextSearch" class="px-5 py-2 bg-blue-600 text-white rounded-full hover:bg-blue-500 transition-colors whitespace-nowrap text-sm">搜索</button>
          </div>

          <!-- Image Search Mode -->
          <div v-if="currentTab === 'image'" class="w-full flex justify-end">
              <div 
                @click="$refs.fileInput.click()"
                class="border border-[#333] rounded-lg px-4 py-2 cursor-pointer hover:bg-[#1a1a1a] hover:border-blue-500 transition-colors bg-[#0f0f0f] flex items-center gap-3 group"
              >
                  <div class="text-xl group-hover:scale-110 transition-transform">🖼️</div>
                  <div class="text-sm text-gray-400 group-hover:text-white transition-colors">点击上传图片</div>
                  <input type="file" ref="fileInput" class="hidden" @change="doImageSearch" accept="image/*" />
              </div>
          </div>

          <!-- AI Search Mode -->
          <div v-if="currentTab === 'ai'" class="w-full">
              <!-- Step 1: Input -->
              <div v-if="!generatedImage" class="flex gap-2">
                  <input 
                      v-model="aiPrompt" 
                      class="flex-1 border border-[#333] rounded-lg px-4 py-2 focus:ring-1 focus:ring-purple-500 focus:border-purple-500 bg-[#1a1a1a] text-white placeholder-gray-600"
                      placeholder="描述画面..."
                      @keydown.enter="doGenerate"
                  >
                  <button 
                    @click="doGenerate" 
                    :disabled="!aiPrompt || aiLoading"
                    class="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-500 disabled:opacity-50 flex items-center gap-2 whitespace-nowrap text-sm transition-colors"
                  >
                      <span v-if="aiLoading" class="animate-spin">🌀</span>
                      <span>{{ aiLoading ? '生成中' : '✨ 生成' }}</span>
                  </button>
              </div>

              <!-- Step 2: Confirm -->
              <div v-else class="flex items-center gap-2 justify-end w-full">
                  <img :src="generatedImage" @click="viewGeneratedImage = true" class="h-10 w-10 object-cover rounded border border-[#333] bg-[#1a1a1a] cursor-zoom-in hover:opacity-80 transition-opacity" />
                  <div class="flex-1 text-xs text-gray-500 truncate text-right mr-2">{{ aiPrompt }}</div>
                  
                  <button @click="doSearchGenerated" class="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-500 whitespace-nowrap transition-colors">
                      🔍 搜索
                  </button>
                  <button @click="generatedImage = null" class="px-3 py-1.5 text-gray-500 hover:bg-[#1a1a1a] hover:text-gray-300 text-sm rounded whitespace-nowrap transition-colors">
                      重试
                  </button>
              </div>
          </div>
      </div>


      <!-- Full Image Preview Modal -->
      <div v-if="viewGeneratedImage && generatedImage" class="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4 backdrop-blur-sm" @click.self="viewGeneratedImage = false">
           <div class="relative max-w-full max-h-full">
               <button @click="viewGeneratedImage = false" class="absolute -top-10 right-0 text-white text-3xl font-light hover:text-gray-300 transition-colors">✕</button>
               <img :src="generatedImage" class="max-w-full max-h-[90vh] object-contain rounded shadow-2xl" />
           </div>
      </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { searchState } from '../store'
import axios from 'axios'

const query = ref('')

// ---- Search history (device-local) ----
const HISTORY_KEY = 'dp_search_history'
const showHistory = ref(false)
const history = ref([])
try { history.value = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') } catch (e) { history.value = [] }

const persistHistory = () => {
    try { localStorage.setItem(HISTORY_KEY, JSON.stringify(history.value)) } catch (e) { /* quota/private mode */ }
}
const rememberQuery = (q) => {
    q = (q || '').trim()
    if (!q) return
    history.value = [q, ...history.value.filter(x => x !== q)].slice(0, 20)
    persistHistory()
}
const removeHistory = (q) => {
    history.value = history.value.filter(x => x !== q)
    persistHistory()
}
const clearHistory = () => { history.value = []; persistHistory() }
const searchFromHistory = (q) => {
    query.value = q
    showHistory.value = false
    doTextSearch()
}
const currentTab = ref('text') // text, image, ai
const API_BASE = 'http://localhost:8001'

// AI State
const aiPrompt = ref('')
const aiLoading = ref(false)
const generatedImage = ref(null) // Base64 string
const viewGeneratedImage = ref(false)

const resetTimeline = () => {
    searchState.reset()
    query.value = ''
    generatedImage.value = null
    aiPrompt.value = ''
}

const onBlur = () => {
    if (!query.value.trim() && searchState.mode === 'search') {
        // Only reset if we were in search mode but now box is empty
        // Actually user said "Clear box -> blur -> reset".
        // If box is empty, query is empty.
        resetTimeline()
    }
}

const doTextSearch = async () => {
    if (!query.value.trim()) return
    rememberQuery(query.value)
    showHistory.value = false
    searchState.setLoading(true)
    const start = performance.now()
    try {
        const res = await axios.post(`${API_BASE}/search/text`, { query: query.value })
        const duration = ((performance.now() - start) / 1000).toFixed(3)
        // Backend now returns { results: [], translated_query: "..." }
        searchState.setResults(res.data.results, query.value, duration, res.data.translated_query)
    } catch (e) {
        console.error(e)
        alert('Search failed')
    } finally {
        searchState.setLoading(false)
    }
}

const doImageSearch = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    
    // Reset input just in case
    e.target.value = '' 
    
    await executeImageSearch(file, 'Image Search')
}

// Low level image search
const executeImageSearch = async (fileBlob, title) => {
    const formData = new FormData()
    formData.append('file', fileBlob)
    
    searchState.setLoading(true)
    const start = performance.now()
    try {
        const res = await axios.post(`${API_BASE}/search/image`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        })
        const duration = ((performance.now() - start) / 1000).toFixed(3)
        searchState.setResults(res.data, title, duration)
    } catch (e) {
        console.error(e)
        alert('Search failed')
    } finally {
        searchState.setLoading(false)
    }
}

const doGenerate = async () => {
    if (!aiPrompt.value) return
    aiLoading.value = true
    try {
        const res = await axios.post(`${API_BASE}/generate`, { prompt: aiPrompt.value })
        if (res.data && res.data.image) {
            generatedImage.value = res.data.image
        }
    } catch (e) {
        console.error(e)
        alert('Generation failed: ' + (e.response?.data?.detail || e.message))
    } finally {
        aiLoading.value = false
    }
}

const doSearchGenerated = async () => {
    if (!generatedImage.value) return
    
    // Convert base64 to blob
    try {
        const fetchRes = await fetch(generatedImage.value)
        const blob = await fetchRes.blob()
        await executeImageSearch(blob, `AI: ${aiPrompt.value}`)
        // Clean up UI but keep results
        // generatedImage.value = null 
    } catch (e) {
        alert("Converting image failed")
    }
}

</script>
