<template>
  <div class="h-full flex flex-col bg-gray-900">
    <!-- Header -->
    <div class="bg-gray-900 border-b border-gray-800 px-6 py-4 flex items-center justify-between shadow-sm z-10">
      <div class="flex items-center gap-4">
        <button v-if="selectedPerson" @click="selectedPerson = null" class="text-gray-300 hover:text-white">
           ← 返回
        </button>
        <span class="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-400 to-indigo-400">
          {{ selectedPerson ? selectedPerson.name : '人物 (People)' }}
        </span>
        <span v-if="selectedPerson" class="text-sm text-gray-400 bg-gray-800 px-2 py-1 rounded-full">
            {{ photos.length }} photos
        </span>
        <!-- Moved Delete Button -->
        <button 
            v-if="selectedPerson"
            @click.stop="confirmDelete(selectedPerson)"
            class="flex items-center gap-1.5 px-3 py-1 bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white border border-red-500/20 rounded-full text-xs font-medium transition-all shadow-sm"
            title="删除此分类"
        >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M6 18L18 6M6 6l12 12" />
            </svg>
            删除人物分类
        </button>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto p-6 scroll-smooth">
        <Transition name="fade" mode="out-in">
            <!-- Loading Skeleton -->
            <div v-if="loading && !selectedPerson" key="loading" class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-6 animate-pulse">
                <div v-for="i in 16" :key="i" class="flex flex-col items-center">
                    <div class="w-32 h-32 bg-gray-800 rounded-full mb-3"></div>
                    <div class="w-20 h-4 bg-gray-800 rounded mb-2"></div>
                    <div class="w-12 h-3 bg-gray-800 rounded opacity-50"></div>
                </div>
            </div>

            <!-- Detail View Skeleton -->
            <div v-else-if="loading && selectedPerson" key="loading-detail" class="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2 animate-pulse">
                <div v-for="i in 12" :key="i" class="aspect-square bg-gray-800 rounded-lg"></div>
            </div>
            
            <!-- People Grid -->
            <div v-else-if="!selectedPerson" key="people-grid">
                <div class="flex justify-end mb-4" v-if="filteredPeople.length > 1">
                    <button @click="toggleMergeMode"
                            class="text-sm px-3 py-1.5 rounded-lg border transition-colors"
                            :class="mergeMode ? 'border-blue-500 text-blue-400 bg-blue-500/10' : 'border-line-strong text-gray-400 hover:text-gray-200'">
                        {{ mergeMode ? '退出合并' : '合并人物' }}
                    </button>
                </div>
                <div v-if="mergeMode" class="text-xs text-gray-500 mb-3">
                    同一个人被分成多组时：点选要合并的人物（第一个选中的为保留项），然后点击下方"合并"。
                </div>
                <EmptyState v-if="filteredPeople.length === 0" :icon="Users"
                    title="还没有识别到人物"
                    description="索引完成后，AI 会自动检测照片中的人脸并按人物分组。" />
                <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-6">
                    <div 
                        v-for="person in filteredPeople" 
                        :key="person.id"
                        class="group flex flex-col items-center relative"
                    >
                        <div 
                            class="relative w-32 h-32 mb-3 rounded-full overflow-hidden border-4 border-gray-700 shadow-md group-hover:border-purple-500 group-hover:shadow-lg transition-all duration-300 cursor-pointer"
                            @click="mergeMode ? toggleMergePick(person) : selectPerson(person)"
                            :class="mergeMode && mergePicks.includes(person.id) ? (mergePicks[0] === person.id ? 'ring-2 ring-green-500 rounded-full' : 'ring-2 ring-blue-500 rounded-full') : ''"
                        >
                            <img 
                                loading="lazy"
                                :src="`http://localhost:8001/files/face/thumbnail/${person.cover_face_id}`" 
                                class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110" 
                            />
                        </div>
                        <div class="flex items-center gap-1 group/name">
                            <input 
                                v-if="editingId === person.id"
                                v-model="newName"
                                @blur="saveName(person)"
                                @keyup.enter="saveName(person)"
                                ref="nameInput"
                                class="text-sm font-medium text-center bg-gray-800 text-white border-b border-purple-500 outline-none w-24 px-1"
                                autofocus
                            />
                            <div 
                                v-else 
                                class="font-medium text-gray-300 transition-colors group-hover:text-purple-400 truncate max-w-[120px]"
                            >
                                {{ person.name }}
                            </div>
                            <button 
                                v-if="editingId !== person.id" 
                                @click="startEdit(person)"
                                class="text-gray-500 hover:text-purple-400 opacity-0 group-hover/name:opacity-100 transition-opacity"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                                    <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
                                </svg>
                            </button>
                        </div>
                        <div class="text-xs text-gray-500">{{ person.count }} photos</div>
                    </div>
                </div>

                <!-- Pagination -->
                <div v-if="totalPages > 1" class="mt-12 flex flex-col items-center gap-4 pb-16">
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
                                        ? 'bg-purple-600 border-purple-500 text-white shadow-lg shadow-purple-900/20' 
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
                        第 {{ currentPage }} 页 / 共 {{ totalPages }} 页 ({{ totalCount }} 位人物)
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
        <div v-if="!loading && !selectedPerson && people.length === 0" class="flex flex-col items-center justify-center h-full text-gray-400">
             <div class="text-5xl mb-4 text-gray-700">👥</div>
             <p class="font-medium">未发现人物</p>
             <p class="text-xs mt-2 opacity-50">请确保已索引含有这类照片的文件夹</p>
        </div>
    </div>
  </div>
</template>

<script setup>
import EmptyState from '../components/EmptyState.vue'
import { toast } from '../composables/useToast'
import { Users } from 'lucide-vue-next'
import { ref, onMounted, nextTick, computed } from 'vue'
import { searchState } from '../store'

const people = computed(() => searchState.peopleData || [])
const filteredPeople = computed(() => searchState.peopleData || [])
const selectedPerson = ref(null)
const photos = ref([])
const loading = ref(false)
const hasMore = ref(true)
const currentPage = ref(1)
const totalCount = ref(0)
const pageSize = 100
const API_BASE = 'http://localhost:8001'

// ---- Cluster merge (DBSCAN routinely splits one person) ----
const mergeMode = ref(false)
const mergePicks = ref([])
const merging = ref(false)

const toggleMergeMode = () => {
    mergeMode.value = !mergeMode.value
    mergePicks.value = []
}
const toggleMergePick = (person) => {
    const i = mergePicks.value.indexOf(person.id)
    if (i === -1) mergePicks.value.push(person.id)
    else mergePicks.value.splice(i, 1)
}
const doMerge = async () => {
    const [target, ...sources] = mergePicks.value
    merging.value = true
    try {
        for (const source of sources) {
            await axios.post(`${API_BASE}/files/organize/people/merge`,
                             { source_id: source, target_id: target })
        }
        toast(`已合并 ${sources.length} 组人物`)
        mergeMode.value = false
        mergePicks.value = []
        await fetchPeople()
    } catch (e) {
        toast('合并失败', { type: 'error' })
    } finally {
        merging.value = false
    }
}

const editingId = ref(null)
const newName = ref('')
const nameInput = ref(null)

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

const fetchPeople = async (targetPage = 1) => {
    if (targetPage === 1 && !searchState.peopleLoaded) {
        // Initial load
    }
    
    loading.value = true

    try {
        const res = await fetch(`${API_BASE}/files/organize/people?page=${targetPage}&page_size=${pageSize}`)
        const data = await res.json()
        
        const items = data.items || (Array.isArray(data) ? data : [])
        const total = data.total || items.length
        
        // Refresh mode: replace instead of append
        searchState.peopleData = items
        currentPage.value = targetPage
        totalCount.value = total
        
        hasMore.value = searchState.peopleData.length < total
        searchState.peopleLoaded = true
        
        // Scroll to top of grid
        nextTick(() => {
            const container = document.querySelector('.overflow-y-auto')
            if (container) container.scrollTop = 0
        })
    } catch (e) {
        console.error(e)
    } finally {
        loading.value = false
    }
}

const goToPage = (p) => {
    if (p === '...' || p === currentPage.value) return
    fetchPeople(p)
}

const fetchMore = () => {
    // Legacy function, replaced by digital pagination
}

const startEdit = (person) => {
    editingId.value = person.id
    newName.value = person.name.startsWith('Person ') ? '' : person.name
    nextTick(() => {
        if (nameInput.value && nameInput.value[0]) nameInput.value[0].focus()
    })
}

const saveName = async (person) => {
    const targetName = newName.value.trim()
    if (!targetName) {
        editingId.value = null
        return
    }
    
    try {
        await fetch('http://localhost:8001/files/organize/people/name', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ person_id: person.id, name: targetName })
        })
        person.name = targetName
    } catch (e) {
        console.error(e)
    } finally {
        editingId.value = null
    }
}

const confirmDelete = async (person) => {
    if (!confirm(`确定要删除人物分类 "${person.name}" 吗？此操作不可恢复。`)) return
    
    try {
        const res = await fetch(`${API_BASE}/files/organize/people/delete/${person.id}`, {
            method: 'DELETE'
        })
        searchState.peopleData = searchState.peopleData.filter(p => p.id !== person.id)
    } catch (e) {
        console.error(e)
    }
}

const selectPerson = async (person) => {
    selectedPerson.value = person
    loading.value = true
    try {
        const res = await fetch(`${API_BASE}/files/organize/people/${person.id}`)
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
    fetchPeople()
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
