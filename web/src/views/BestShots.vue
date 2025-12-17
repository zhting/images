<template>
  <div class="p-6">
    <h1 class="text-3xl font-bold mb-6 flex items-center gap-2">
      🌟 相似图优选 (Best Shots)
    </h1>
    
    <div v-if="loading" class="text-center py-20 text-gray-500">
        加载中...
    </div>
    
    <div v-else-if="groups.length === 0" class="text-center py-20 text-gray-500">
        太棒了！没有发现重复的连拍照片。
    </div>
    
    <div class="space-y-12">
        <div v-for="group in groups" :key="group.id" class="bg-white rounded-xl shadow-sm border p-6">
            <div class="flex justify-between items-center mb-4">
                <div class="text-gray-500 font-mono text-sm">
                    {{ formatTime(group.items[0].captured_time) }} · {{ group.items.length }} 张连拍
                </div>
                <button class="text-sm text-red-500 hover:bg-red-50 px-3 py-1 rounded border border-red-200">
                    一键清理其他
                </button>
            </div>
            
            <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                <div v-for="item in group.items" :key="item.file_path" class="relative group cursor-pointer">
                    <!-- Image -->
                    <div class="aspect-square rounded-lg overflow-hidden border-2 transition-all relative"
                         :class="item.is_best ? 'border-amber-400 ring-2 ring-amber-100' : 'border-transparent opacity-80 hover:opacity-100'">
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
                    <div class="absolute top-2 left-2 z-10" v-if="!item.is_best">
                        <input type="checkbox" class="w-5 h-5 rounded border-gray-300 text-red-500 focus:ring-red-500" checked>
                    </div>
                </div>
            </div>
        </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const groups = ref([])
const loading = ref(true)
const API_BASE = 'http://localhost:8000'

const formatTime = (ts) => {
    return new Date(ts * 1000).toLocaleString()
}

const fetchBestShots = async () => {
    try {
        const res = await axios.get(`${API_BASE}/files/organize/best_shots`)
        groups.value = res.data
    } catch (e) {
        alert("Failed to load best shots: " + e.message)
    } finally {
        loading.value = false
    }
}

onMounted(() => {
    fetchBestShots()
})
</script>
