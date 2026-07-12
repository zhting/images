<template>
    <!-- Top Bar -->
    <TopBar />

    <div class="px-4 pb-20 pt-6"> <!-- content wrapper -->
        
        <!-- Loading State -->
        <div v-if="loading || searchState.loading" class="text-center py-10">
            <span class="animate-pulse text-xl text-gray-400">加载中…</span>
        </div>

        <!-- First run: nothing indexed yet -> onboarding flow -->
        <Onboarding
            v-else-if="searchState.mode === 'timeline' && totalItems === 0"
            :api-base="API_BASE"
            @refresh="reloadTimeline"
        />

        <!-- 1. Timeline View -->
        <div v-else-if="searchState.mode === 'timeline'" class="timeline-container relative">
            <!-- Vertical Line (Visible now, z-0) -->
            <div class="absolute left-4 md:left-[8.5rem] top-0 bottom-0 w-[1px] bg-[#333] z-0"></div>

            <!-- Top Sentinel for Upward Scroll -->
            <div ref="topTrigger" class="h-4 w-full"></div>

            <div v-for="group in timelineGroups" :key="group.key" class="mb-8 flex flex-col md:flex-row gap-4 relative z-10 timeline-group">

                 <!-- Date Label (Left sticky) -->
                <div class="md:w-32 flex-shrink-0 text-right pr-4 hidden md:block pt-1">
                     <div class="sticky top-[4.5rem] transition-all cursor-pointer group" @click="showDateSelector(group.key)">
                        <span class="font-bold text-[#ececec] text-lg block group-hover:text-blue-400 transition-colors">{{ group.key }} ▾</span>
                        <div class="text-xs text-gray-500 mt-1">{{ group.items.length }} items</div>
                     </div>
                </div>
                <!-- Mobile Date Label -->
                <div class="pl-8 md:hidden mb-2">
                     <span class="font-bold text-[#ececec]">{{ group.key }}</span> <span class="text-xs text-gray-500">({{ group.items.length }})</span>
                </div>
                
                <!-- Timeline Dot (Hollow style, z-10) -->
                <div class="absolute left-4 md:left-[8.5rem] top-2 w-2 h-2 bg-[#0f0f0f] rounded-full border-2 border-gray-600 shadow-sm -translate-x-1/2"></div>

                <!-- Grid -->
                <div class="flex-1">
                    <div class="month-grid grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8 gap-1">
                        <div v-for="(item, index) in group.items" :key="item.file_path" class="relative group cursor-pointer aspect-square bg-[#1a1a1a] overflow-hidden" @click="openGallery(group.items, index)">
                            <img :src="getThumbUrl(item.file_path)" 
                                 class="w-full h-full object-cover transition-opacity duration-300 hover:opacity-90" 
                                 :loading="(timelineGroups.indexOf(group) === 0 && index < 12) ? 'eager' : 'lazy'" 
                                 decoding="async" />
                            
                            <!-- Video Indicator -->
                            <div v-if="item.tag === 'video'" class="absolute inset-0 flex items-center justify-center pointer-events-none">
                                <div class="bg-black/30 rounded-full p-1.5 backdrop-blur-[2px]">
                                    <svg class="w-4 h-4 text-white translate-x-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                                </div>
                            </div>

                            <!-- Burst Badge -->
                             <div v-if="item.similar_count > 0" class="absolute top-1 right-1 bg-black/60 text-white text-[9px] px-1.5 rounded-sm backdrop-blur-sm">
                                 +{{ item.similar_count }}
                             </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Sentinel for Infinite Scroll verification -->
            <div ref="loadTrigger" class="h-4 w-full"></div>
            
            <!-- Skeleton Loader -->
            <div v-if="fetching" class="mb-8">
                <div class="month-grid grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8 gap-1">
                    <div v-for="n in 12" :key="n" class="aspect-square bg-[#1a1a1a] skeleton-pulse"></div>
                </div>
            </div>
            <div v-if="!hasMore && items.length > 0" class="text-center py-12 text-gray-700 text-xs tracking-wider uppercase">
                End of timeline
            </div>
        </div>

        <!-- 2. Search View -->
        <div v-else-if="searchState.mode === 'search'" class="search-container">
            <div class="mb-4 flex items-center justify-between">
                <h3 class="text-xl font-bold flex items-baseline gap-2">
                    搜索: "{{ searchState.query }}"
                    <span v-if="searchState.translatedQuery" class="text-gray-500 text-sm font-normal">
                        ({{ searchState.translatedQuery }})
                    </span>
                </h3>
                <span class="text-gray-500">
                    {{ searchState.results.length }} 个结果
                    <span v-if="searchState.duration" class="ml-2 text-sm bg-gray-100 px-2 py-0.5 rounded">
                        耗时 {{ searchState.duration }}s
                    </span>
                </span>
            </div>

            <div v-if="searchState.results.length === 0" class="text-center py-20 text-gray-500">
                <div class="text-4xl mb-4">🤔</div>
                没有找到相关照片
            </div>
            
            <div class="month-grid grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2">
                <div v-for="(item, index) in searchState.results" :key="item.file_path" class="relative group cursor-pointer" @click="openGallery(searchState.results, index)">
                    <img :src="getThumbUrl(item.file_path)" class="w-full h-40 object-cover rounded shadow-sm hover:opacity-90 transition-none" loading="lazy" />
                    <div class="absolute bottom-0 left-0 right-0 bg-black/50 text-white text-xs p-1 truncate">
                        <div class="flex justify-between items-center">
                            <span class="truncate pr-2 flex-1">{{ item.basename }}</span>
                            <span class="opacity-90 flex-shrink-0 bg-black/30 px-1 rounded">相似度 {{ (item.score * 100).toFixed(2) }}%</span>
                        </div>
                    </div>
                    
                    <!-- Video Indicator -->
                    <div v-if="item.tag === 'video'" class="absolute center-center top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none">
                         <div class="bg-black/40 rounded-full p-2 backdrop-blur-sm">
                            <svg class="w-6 h-6 text-white translate-x-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
    </div>

    <!-- Gallery Modal -->
    <PhotoViewer
        v-if="gallery.open"
        :items="gallery.currentItems"
        :start-index="gallery.currentIndex"
        :api-base="API_BASE"
        @close="closeGallery"
        @trash="onViewerTrash"
        @index-change="i => gallery.currentIndex = i"
    />
    <!-- Date Jump Modal -->
    <div v-if="showDateJump" class="fixed inset-0 z-[60] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4" @click.self="showDateJump = false">
        <div class="bg-[#1a1a1a] border border-[#333] rounded-xl max-w-sm w-full max-h-[80vh] flex flex-col shadow-2xl">
            <div class="p-4 border-b border-[#333] flex justify-between items-center">
                <h3 class="text-white font-bold text-lg">Jump to Date</h3>
                <button @click="showDateJump = false" class="text-gray-400 hover:text-white text-2xl">✕</button>
            </div>
            
            <div class="overflow-y-auto p-4 custom-scrollbar flex-1">
                <div v-for="year in availableYears" :key="year" class="mb-6">
                    <div class="text-blue-500 font-bold text-xl mb-3 sticky top-0 bg-[#1a1a1a] py-1">{{ year }}</div>
                    <div class="grid grid-cols-4 gap-2">
                        <button 
                            v-for="g in getMonthsForYear(year)" 
                            :key="g.key"
                            @click="jumpToDate(g)"
                            class="px-2 py-2 rounded bg-[#222] hover:bg-[#333] text-gray-300 hover:text-white text-sm transition-colors text-center border border-transparent hover:border-blue-500/50"
                        >
                            <div class="font-bold">{{ g.key.split('-')[1] }}</div>
                            <div class="text-[10px] text-gray-500">{{ g.count }}</div>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'
import PhotoViewer from './PhotoViewer.vue'
import Onboarding from './Onboarding.vue'
import { toast } from '../composables/useToast'
import axios from 'axios'
import TopBar from './TopBar.vue'
import { searchState } from '../store'

const timelineGroups = ref([]) // Buffered groups { key: '2023-01', items: [] }
const items = ref([]) // Kept for consistency if needed, but mainly we use timelineGroups now

const loading = ref(true)
const fetching = ref(false)
const fetchingPrev = ref(false)
const nextPage = ref(1)
const prevPage = ref(0)
const hasMore = ref(true)
const hasPrev = ref(false)
const totalItems = ref(0)
const API_BASE = 'http://localhost:8001'

const gallery = ref({
    open: false,
    currentItems: [], // Flat list of items in the current context (e.g. Month or Search Results)
    currentIndex: 0,
    currentImage: ''
})


// Sentinel for Infinite Scroll
// Sentinel for Infinite Scroll
const loadTrigger = ref(null)
const topTrigger = ref(null)

// Intersection Observer
let observer = null

const setupObserver = () => {
    const options = {
        root: null, // viewport
        rootMargin: '200px',
        threshold: 0.1
    }

    observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                if (entry.target === loadTrigger.value) {
                    // Bottom sentinel -> load next page
                    if (searchState.mode === 'timeline' && !fetching.value && hasMore.value) {
                        loadMore()
                    }
                } else if (entry.target === topTrigger.value) {
                     // Top sentinel -> load prev page
                     if (searchState.mode === 'timeline' && !fetchingPrev.value && hasPrev.value) {
                         loadPrev()
                     }
                }
            }
        })
    }, options)

    if (loadTrigger.value) {
        observer.observe(loadTrigger.value)
    }
    if (topTrigger.value) {
        observer.observe(topTrigger.value)
    }
}

const addToGroups = (newItems, mode = 'append') => {
    if (!newItems || newItems.length === 0) return

    // Pre-calculate groups for new items
    const newGroupsMap = {}
    const newGroupKeys = [] // to keep order

    newItems.forEach(item => {
        const dt = new Date(item.captured_time * 1000)
        const key = isNaN(dt.getTime()) ? 'Unknown' : `${dt.getFullYear()}-${String(dt.getMonth()+1).padStart(2, '0')}`
        if (!newGroupsMap[key]) {
            newGroupsMap[key] = []
            newGroupKeys.push(key)
        }
        newGroupsMap[key].push(item)
    })

    if (mode === 'append') {
        newGroupKeys.forEach(key => {
            const lastGroup = timelineGroups.value[timelineGroups.value.length - 1]
            if (lastGroup && lastGroup.key === key) {
                lastGroup.items.push(...newGroupsMap[key])
            } else {
                timelineGroups.value.push({ key: key, items: newGroupsMap[key] })
            }
        })
    } else { // prepend
        // For prepend: user is scrolling UP, loading OLDER pages (wait, logic check)
        // loadPrev usually loads PREVIOUS page. 
        // If time is DESC (default), Page 2 is OLDER than Page 1.
        // Wait, "Top Sentinel" -> load prev page.
        // If we are at Page 5, we load Page 4 (Newer).
        // Yes, prevPage = 0 (Newer).
        // So newItems are NEWER. 
        // We want to prepend them to the top.
        // newGroupKeys will be ordered DESC (New -> Old).
        
        const generated = newGroupKeys.map(k => ({ key: k, items: newGroupsMap[k] }))
        
        if (generated.length > 0 && timelineGroups.value.length > 0) {
            const lastGen = generated[generated.length - 1]
            const firstExisting = timelineGroups.value[0]
            
            if (lastGen.key === firstExisting.key) {
                // Merge intersection
                firstExisting.items.unshift(...lastGen.items)
                generated.pop()
            }
        }
        
        if (generated.length > 0) {
            timelineGroups.value.unshift(...generated)
        }
    }
}

const loadMore = async () => {
    if (fetching.value || !hasMore.value) return
    fetching.value = true
    
    try {
        const res = await axios.get(`${API_BASE}/timeline`, {
            params: {
                page: nextPage.value,
                size: 50
            }
        })
        
        const newItems = res.data.items || []
        const total = res.data.total || 0
        totalItems.value = total
        
        if (newItems.length > 0) {
            // items.value.push(...newItems)
            addToGroups(newItems, 'append')
            nextPage.value++
        } else {
            hasMore.value = false
        }
        
        // Check if we have reached the end based on logical page index
        // page.value (nextPage) is already incremented, so we check if (nextPage-1) * 50 >= total
        if ((nextPage.value - 1) * 50 >= totalItems.value) {
            hasMore.value = false
        }
        
    } catch (e) {
        console.error("Load timeline failed", e)
    } finally {
        fetching.value = false
        loading.value = false
    }
}

const loadPrev = async () => {
    if (fetchingPrev.value || !hasPrev.value) return
    fetchingPrev.value = true
    
    // Capture scroll height before prepend
    const scroller = document.getElementById('main-scroller')
    // if (!scroller) return // allow running without scroller if needed

    const oldHeight = scroller ? scroller.scrollHeight : 0
    const oldTop = scroller ? scroller.scrollTop : 0
    
    try {
        const res = await axios.get(`${API_BASE}/timeline`, {
            params: {
                page: prevPage.value,
                size: 50
            }
        })
        
        const newItems = res.data.items || []
        if (newItems.length > 0) {
            // items.value.unshift(...newItems)
            addToGroups(newItems, 'prepend')
            
            prevPage.value--
            if (prevPage.value < 1) hasPrev.value = false
            
            // Restore scroll position
            nextTick(() => {
                if(scroller) {
                    const newHeight = scroller.scrollHeight
                    const diff = newHeight - oldHeight
                    scroller.scrollTop = oldTop + diff
                }
            })
        } else {
            hasPrev.value = false
        }

    } catch (e) {
         console.error("Load prev failed", e)
    } finally {
        fetchingPrev.value = false
    }
}

// Initial Fetch
const reloadTimeline = async () => {
    timelineGroups.value = []
    totalItems.value = 0
    nextPage.value = 1
    prevPage.value = 0
    hasMore.value = true
    hasPrev.value = false
    await loadMore()
    nextTick(() => setupObserver())
}

onMounted(async () => {
    await loadMore()
    
    // Setup observer after initial data might have loaded, but it's safe to setup anytime.
    // Ideally wait for DOM update if trigger is conditional, but here it is always rendered at bottom.
    nextTick(() => {
        setupObserver()
    })
})

onUnmounted(() => {
    if (observer) {
        observer.disconnect()
    }
})

// Group by Month (computed)
// Grouping logic removed in favor of timelineGroups


const getFileUrl = (path) => {
    return `${API_BASE}/files/content?path=${encodeURIComponent(path)}`
}

const getThumbUrl = (path, size = 'grid') => {
    return `${API_BASE}/files/thumbnail?path=${encodeURIComponent(path)}&size=${size}`
}

// Gallery Logic
const openGallery = (sourceItems, index) => {
    // PhotoViewer owns progressive loading, preloading, keyboard
    // handling and the body scroll lock.
    gallery.value.currentItems = sourceItems
    gallery.value.currentIndex = index
    gallery.value.open = true
}

// Viewer emitted trash: optimistic removal + undoable toast.
const onViewerTrash = async (item) => {
    const galleryIdx = gallery.value.currentItems.indexOf(item)
    const groupKey = item.captured_time
        ? `${new Date(item.captured_time * 1000).getFullYear()}-${String(new Date(item.captured_time * 1000).getMonth() + 1).padStart(2, '0')}`
        : 'Unknown'
    const group = timelineGroups.value.find(g => g.key === groupKey)
    const groupIdx = group ? group.items.findIndex(i => i.file_path === item.file_path) : -1
    const groupPos = group ? timelineGroups.value.indexOf(group) : -1

    // Optimistic removal: let the rare failure pay the wait, not
    // every successful delete.
    if (group && groupIdx !== -1) {
        group.items.splice(groupIdx, 1)
        totalItems.value--
        if (group.items.length === 0) timelineGroups.value.splice(groupPos, 1)
    }
    if (galleryIdx !== -1) gallery.value.currentItems.splice(galleryIdx, 1)

    const reinsert = () => {
        if (group && groupIdx !== -1) {
            if (!timelineGroups.value.includes(group)) {
                timelineGroups.value.splice(Math.min(groupPos, timelineGroups.value.length), 0, group)
            }
            group.items.splice(Math.min(groupIdx, group.items.length), 0, item)
            totalItems.value++
        }
        if (galleryIdx !== -1) {
            gallery.value.currentItems.splice(Math.min(galleryIdx, gallery.value.currentItems.length), 0, item)
        }
    }

    try {
        await axios.post(`${API_BASE}/files/trash`, { file_paths: [item.file_path] })
        toast('已移入回收站', {
            actionLabel: '撤销',
            duration: 6000,
            onAction: async () => {
                try {
                    await axios.post(`${API_BASE}/files/restore`, { file_paths: [item.file_path] })
                    reinsert()
                } catch (e) {
                    toast('恢复失败', { type: 'error' })
                }
            },
        })
    } catch (e) {
        reinsert()
        toast('删除失败', { type: 'error' })
    }
}

const closeGallery = () => {
    gallery.value.open = false
}

// Date Jumping Logic
const dateGroups = ref([]) // From backend
const showDateJump = ref(false)

const loadDateGroups = async () => {
    try {
        const res = await axios.get(`${API_BASE}/timeline/dates`)
        dateGroups.value = res.data
    } catch (e) {
        console.error("Failed to load dates", e)
    }
}

// Computes unique years for the selector
const availableYears = computed(() => {
    const years = new Set()
    dateGroups.value.forEach(g => {
        if(g.key !== 'Unknown') {
            years.add(g.key.split('-')[0])
        }
    })
    return Array.from(years).sort().reverse() // Newest first
})

const getMonthsForYear = (year) => {
    return dateGroups.value.filter(g => g.key.startsWith(year))
}

const showDateSelector = (currentKey) => {
    // Force reload to ensure indices are fresh (in case of deletes/re-index)
    loadDateGroups()
    showDateJump.value = true
}

const jumpToDate = (group) => {
    // Calculate target page
    const targetPage = Math.floor(group.index / 50) + 1
    
    console.log(`Jumping to ${group.key}, index ${group.index}, page ${targetPage}`)
    
    // Reset and reload
    // Reset and reload
    timelineGroups.value = []

    
    // Set pointers
    // We will load targetPage immediately.
    // nextPage will be targetPage + 1
    // prevPage will be targetPage - 1
    nextPage.value = targetPage
    prevPage.value = targetPage - 1
    
    fetching.value = false
    hasMore.value = true
    hasPrev.value = (prevPage.value >= 1)
    
    showDateJump.value = false
    
    loadMore() // This uses nextPage, so it loads targetPage and increments nextPage
    
    // Scroll top after reload
    nextTick(() => {
        const scroller = document.getElementById('main-scroller')
        if (scroller) scroller.scrollTop = 0
    })
}

onMounted(async () => {
    loadDateGroups() // Preload for smoother experience
    await loadMore()
    
    nextTick(() => {
        setupObserver()
    })
})

</script>




<style scoped>
/* Hidden Scrollbar for cleaner look */
div::-webkit-scrollbar {
  height: 8px;
  background-color: #000;
}
div::-webkit-scrollbar-thumb {
  background-color: #333;
  border-radius: 4px;
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.skeleton-pulse {
  background: linear-gradient(90deg, #1a1a1a 25%, #2a2a2a 50%, #1a1a1a 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite linear;
}

/* Optimization: Content Visibility */
.timeline-group {
    content-visibility: auto; 
    contain-intrinsic-size: 500px; /* Estimate height of a month group */
}

</style>
