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

  <PhotoViewer v-if="viewer.open" :items="items" :start-index="viewer.index"
               :allow-trash="false" @close="closeViewer" @index-change="i => viewer.index = i">
    <template #toolbar="{ current }">
      <button v-if="current" @click="restoreOne(current)"
              class="bg-green-700 hover:bg-green-600 text-white text-sm px-3 py-1.5 rounded transition-colors">
        还原
      </button>
    </template>
  </PhotoViewer>
</template>

<script setup>
import { API_BASE } from '../api/base'
import { ref, onMounted } from 'vue'
import axios from 'axios'
import PhotoViewer from '../components/PhotoViewer.vue'
import { usePhotoViewer } from '../composables/usePhotoViewer'
import { toast } from '../composables/useToast'

const items = ref([])
const loading = ref(true)
const selectedItems = ref(new Set())
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

// Preview with the shared viewer; restoring from it removes the photo from
// this list (the viewer follows the array) and offers an undo.
const { viewer, openViewer, closeViewer } = usePhotoViewer(items)
const openGallery = (_list, index) => openViewer(index)

const restoreOne = async (item) => {
    try {
        await axios.post(`${API_BASE}/files/restore`, { file_paths: [item.file_path] })
        const i = items.value.indexOf(item)
        if (i !== -1) items.value.splice(i, 1)
        selectedItems.value.delete(item.file_path)
        toast('已还原', {
            actionLabel: '撤销',
            onAction: async () => {
                try {
                    await axios.post(`${API_BASE}/files/trash`, { file_paths: [item.file_path] })
                    items.value.splice(Math.min(i, items.value.length), 0, item)
                } catch (e) { toast('撤销失败', { type: 'error' }) }
            },
        })
    } catch (e) {
        toast('还原失败', { type: 'error' })
    }
}

onMounted(loadTrash)

</script>
