<template>
  <div class="p-6">
    <h1 class="text-3xl font-bold mb-6 flex items-center gap-2">
      📄 文档归档 (Documents)
    </h1>
    
    <div v-if="loading" class="text-center py-20 text-gray-500">
        加载中...
    </div>
    
    <div v-else-if="docs.length === 0" class="text-center py-20 text-gray-500">
        没有发现文档或截图。
    </div>
    
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
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const docs = ref([])
const loading = ref(true)
const API_BASE = 'http://localhost:8000'

const fetchDocs = async () => {
    try {
        const res = await axios.get(`${API_BASE}/files/organize/documents`)
        docs.value = res.data
    } catch (e) {
        alert("Failed to load documents: " + e.message)
    } finally {
        loading.value = false
    }
}

onMounted(() => {
    fetchDocs()
})
</script>
