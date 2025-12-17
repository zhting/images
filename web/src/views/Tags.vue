<template>
  <div class="h-full flex flex-col bg-gray-50">
    <!-- Header -->
    <div class="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between shadow-sm z-10">
      <div class="flex items-center gap-4">
        <button v-if="selectedTag" @click="selectedTag = null" class="text-gray-500 hover:text-gray-900">
           ← 返回
        </button>
        <span class="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-pink-500 to-rose-500">
          {{ selectedTag ? (selectedTag.display_name || selectedTag.name) : '标签 (Tags)' }}
        </span>
         <span v-if="selectedTag" class="text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
            {{ photos.length }} photos
        </span>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto p-6 scroll-smooth">
        <!-- Tags Cloud / Grid -->
        <div v-if="!selectedTag" class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4 pb-10">
             <div 
                v-for="tag in tags" 
                :key="tag.name"
				class="group relative bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-lg hover:-translate-y-1 hover:border-pink-200 cursor-pointer transition-all duration-300 flex flex-col items-center justify-center min-h-[120px]"
                @click="selectTag(tag)"
            >
                <!-- Badge -->
                <span class="absolute top-3 right-3 bg-gray-50 text-gray-400 text-xs font-mono px-2 py-1 rounded-full group-hover:bg-pink-50 group-hover:text-pink-500 transition-colors">
                    {{ tag.count }}
                </span>

                <!-- Icon/Emoji Placeholder if we had one, for now just text -->
                
                <!-- Main Text -->
                <span class="text-gray-800 font-bold text-lg mb-1 group-hover:text-pink-600 transition-colors text-center">
                    {{ tag.display_name || tag.name }}
                </span>
                
                <!-- Sub Text (English) -->
                <span v-if="tag.display_name && tag.display_name !== tag.name" class="text-xs text-gray-400 font-medium uppercase tracking-wider">
                    {{ tag.name }}
                </span>
            </div>
        </div>

        <!-- Detail View -->
         <div v-else class="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
            <div 
                v-for="photo in photos" 
                :key="photo.file_path"
                class="relative group aspect-square bg-gray-100 rounded-lg overflow-hidden cursor-pointer"
            >
                 <img 
                    loading="lazy"
                    :src="`http://localhost:8000/files/thumbnail?path=${encodeURIComponent(photo.file_path)}`" 
                    class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" 
                />
            </div>
        </div>
        
         <!-- Empty -->
        <div v-if="!loading && !selectedTag && tags.length === 0" class="flex flex-col items-center justify-center h-full text-gray-400">
             <div class="text-5xl mb-4">🏷️</div>
             <p>暂无标签 (No tags found)</p>
        </div>
        
        <!-- Loading -->
        <div v-if="loading" class="fixed inset-0 flex items-center justify-center bg-white/50 z-50">
             <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-pink-500"></div>
        </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const tags = ref([])
const selectedTag = ref(null)
const photos = ref([])
const loading = ref(false)

const fetchTags = async () => {
    loading.value = true
    try {
        const res = await fetch('http://localhost:8000/files/organize/tags')
        tags.value = await res.json()
    } catch (e) {
        console.error(e)
    } finally {
        loading.value = false
    }
}

const selectTag = async (tag) => {
    selectedTag.value = tag
    loading.value = true
    try {
        const res = await fetch(`http://localhost:8000/files/organize/tags/${encodeURIComponent(tag.name)}`)
        photos.value = await res.json()
    } catch (e) {
        console.error(e)
    } finally {
        loading.value = false
    }
}

onMounted(() => {
    fetchTags()
})
</script>
