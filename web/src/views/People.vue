<template>
  <div class="h-full flex flex-col bg-gray-50">
    <!-- Header -->
    <div class="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between shadow-sm z-10">
      <div class="flex items-center gap-4">
        <button v-if="selectedPerson" @click="selectedPerson = null" class="text-gray-500 hover:text-gray-900">
           ← 返回
        </button>
        <span class="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-500 to-indigo-600">
          {{ selectedPerson ? selectedPerson.name : '人物 (People)' }}
        </span>
        <span v-if="selectedPerson" class="text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
            {{ photos.length }} photos
        </span>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto p-6 scroll-smooth">
        
        <!-- People Grid -->
        <div v-if="!selectedPerson" class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-6">
            <div 
                v-for="person in people" 
                :key="person.id"
				class="group flex flex-col items-center cursor-pointer"
                @click="selectPerson(person)"
            >
                <div class="relative w-32 h-32 mb-3 rounded-full overflow-hidden border-4 border-white shadow-md group-hover:border-purple-200 group-hover:shadow-lg transition-all duration-300">
                    <!-- Face Crop (Backend should perform crop ideally, but for now using full image. Wait, faces are small, full image is waste. But I only have full image path. I will implement a CSS crop trick or assume backend helps next time.) -->
                    <!-- Using object-cover is not enough if face is small. -->
                    <img 
                        loading="lazy"
                        :src="`http://localhost:8000/files/thumbnail?path=${encodeURIComponent(person.cover_file_path)}`" 
                        class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110" 
                    />
                </div>
                <div class="font-medium text-gray-800 group-hover:text-purple-600 transition-colors">{{ person.name }}</div>
                <div class="text-xs text-gray-400">{{ person.count }} photos</div>
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
        <div v-if="!loading && !selectedPerson && people.length === 0" class="flex flex-col items-center justify-center h-full text-gray-400">
             <div class="text-5xl mb-4">👥</div>
             <p>未发现人物 (No people found)</p>
             <p class="text-xs mt-2">请确保已索引含有这类照片的文件夹</p>
        </div>
        
        <!-- Loading -->
        <div v-if="loading" class="fixed inset-0 flex items-center justify-center bg-white/50 z-50">
            <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500"></div>
        </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const people = ref([])
const selectedPerson = ref(null)
const photos = ref([])
const loading = ref(false)

const fetchPeople = async () => {
    loading.value = true
    try {
        const res = await fetch('http://localhost:8000/files/organize/people')
        people.value = await res.json()
    } catch (e) {
        console.error(e)
    } finally {
        loading.value = false
    }
}

const selectPerson = async (person) => {
    selectedPerson.value = person
    loading.value = true
    try {
        const res = await fetch(`http://localhost:8000/files/organize/people/${person.id}`)
        photos.value = await res.json()
    } catch (e) {
        console.error(e)
    } finally {
        loading.value = false
    }
}

onMounted(() => {
    fetchPeople()
})
</script>
