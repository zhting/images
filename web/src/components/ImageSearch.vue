<template>
  <div class="max-w-6xl mx-auto">
    <div class="bg-white rounded-lg shadow p-6 mb-8">
      <h2 class="text-2xl font-bold mb-4 flex items-center gap-2">
        <span>🖼️</span> 以图搜图
      </h2>
      
      <div 
        class="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-red-400 hover:bg-red-50 transition-colors"
        @click="triggerFileInput"
        @dragover.prevent
        @drop.prevent="handleDrop"
      >
        <input ref="fileInput" type="file" class="hidden" accept="image/*" @change="handleFileSelect">
        
        <div v-if="!previewUrl" class="space-y-2">
            <div class="text-4xl text-gray-400">📤</div>
            <div class="text-gray-600 font-medium">点击上传或拖拽图片到此处</div>
            <div class="text-xs text-gray-400">支持 JPG, PNG, WEBP</div>
        </div>

        <div v-else class="relative inline-block">
             <img :src="previewUrl" class="max-h-64 rounded shadow border">
             <button @click.stop="clearImage" class="absolute -top-2 -right-2 bg-red-500 text-white rounded-full p-1 w-6 h-6 flex items-center justify-center text-xs shadow hover:bg-red-600">✕</button>
        </div>
      </div>
      
       <div class="mt-4 flex justify-end">
           <button 
            @click="handleSearch" 
            class="bg-red-500 text-white px-8 py-2 rounded font-semibold hover:bg-red-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="loading || !selectedFile"
          >
            {{ loading ? '分析中...' : '开始搜索' }}
          </button>
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
              
          </div>
       </div>
    </div>
    
  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'

const API_BASE = 'http://localhost:8001'

const fileInput = ref(null)
const selectedFile = ref(null)
const previewUrl = ref('')
const loading = ref(false)
const results = ref([])
const hasSearched = ref(false)

const getFileUrl = (path) => {
    return `${API_BASE}/files/content?path=${encodeURIComponent(path)}`
}

const triggerFileInput = () => {
    fileInput.value.click()
}

const handleFileSelect = (e) => {
    const file = e.target.files[0]
    processFile(file)
}

const handleDrop = (e) => {
    const file = e.dataTransfer.files[0]
    processFile(file)
}

const processFile = (file) => {
    if (!file) return
    if (!file.type.startsWith('image/')) {
        alert('请上传图片文件')
        return
    }
    selectedFile.value = file
    previewUrl.value = URL.createObjectURL(file)
    results.value = [] // clear previous
}

const clearImage = () => {
    selectedFile.value = null
    previewUrl.value = ''
    fileInput.value.value = '' // Reset input
    results.value = []
}

const handleSearch = async () => {
    if (!selectedFile.value) return
    loading.value = true
    hasSearched.value = true
    
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    
    try {
        const res = await axios.post(`${API_BASE}/search/image`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            params: { top_k: 20 }
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
