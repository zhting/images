<template>
  <div class="p-4 sm:p-6">
    <div class="flex flex-wrap items-center justify-between gap-3 mb-2">
      <h1 class="text-2xl font-bold flex items-center gap-2 text-content">
        <Sparkles :size="24" class="text-amber-400" /> 连拍优选
      </h1>
      <button v-if="selectedCount > 0" @click="cleanSelected()" :disabled="cleaning"
              class="bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors">
        将勾选的 {{ selectedCount }} 张移入回收站
      </button>
    </div>
    <p v-if="groups.length" class="text-gray-500 text-sm mb-6">
      每组连拍里 AI 推荐保留一张（👑），其余默认勾选。确认后移入回收站，可在回收站或通过「撤销」恢复。点开大图可以改选推荐。
    </p>

    <div v-if="loading" class="text-center py-20 text-gray-500 animate-pulse">加载中…</div>

    <EmptyState v-else-if="groups.length === 0" :icon="Sparkles"
        title="没有发现连拍"
        description="同一时间附近拍下的多张相似照片会出现在这里，方便只留最好的一张。" />

    <div class="space-y-6">
        <div v-for="group in groups" :key="group.id" class="bg-surface-raised border border-line rounded-xl p-4 sm:p-5">
            <div class="flex flex-wrap justify-between items-center gap-2 mb-4">
                <div class="text-gray-400 text-sm">
                    {{ formatTime(group.items[0].captured_time) }} · {{ group.items.length }} 张连拍
                </div>
                <button v-if="groupSelected(group).length" @click="cleanSelected(group)" :disabled="cleaning"
                        class="text-red-400 hover:text-red-300 text-sm disabled:opacity-50">
                    清理此组 {{ groupSelected(group).length }} 张
                </button>
            </div>

            <div class="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-3">
                <div v-for="(item, idx) in group.items" :key="item.file_path" class="relative group cursor-pointer">
                    <div class="aspect-square rounded-lg overflow-hidden border-2 transition-all relative"
                         :class="item.is_best ? 'border-amber-400' : (item.selected ? 'border-transparent opacity-60' : 'border-transparent hover:border-line-stronger')"
                         @click="openGallery(group, idx)">
                         <img :src="`${API_BASE}/files/thumbnail?path=${encodeURIComponent(item.file_path)}`"
                              class="w-full h-full object-cover" loading="lazy" decoding="async">
                         <div class="absolute bottom-1 right-1 bg-black/60 text-white text-[10px] px-1.5 py-0.5 rounded font-mono"
                              title="AI 美学评分">
                             {{ Math.round(item.aesthetic_score * 100) }}
                         </div>
                    </div>
                    <div v-if="item.is_best" class="absolute -top-2 -right-2 bg-amber-400 text-black text-xs px-2 py-0.5 rounded-full shadow-lg z-10 font-medium">
                        👑 推荐保留
                    </div>
                    <label v-else class="absolute top-1.5 left-1.5 z-10 flex items-center justify-center w-6 h-6 rounded-full bg-black/60 cursor-pointer"
                           @click.stop :title="item.selected ? '将移入回收站（点击取消）' : '保留（点击改为清理）'">
                        <input type="checkbox" v-model="item.selected" class="w-4 h-4 accent-red-500 cursor-pointer">
                    </label>
                </div>
            </div>
        </div>

        <div v-if="hasMore" class="flex justify-center pt-4 pb-4">
            <button @click="loadMore" :disabled="loadingMore"
                    class="px-6 py-2 rounded-lg border border-line-strong text-gray-300 hover:bg-surface-hover text-sm transition-colors disabled:opacity-50">
                {{ loadingMore ? '加载中…' : '加载更多' }}
            </button>
        </div>
        <div v-if="!hasMore && groups.length > 0 && !loading" class="text-center py-10 text-gray-600 text-sm">
            没有更多连拍了
        </div>
    </div>
  </div>

  <PhotoViewer
      v-if="gallery.open"
      :items="gallery.currentGroup.items"
      :start-index="gallery.currentIndex"
      :api-base="API_BASE"
      :allow-trash="false"
      @close="closeGallery"
      @index-change="i => gallery.currentIndex = i"
  >
      <template #toolbar>
          <button v-if="!currentGalleryItem.is_best"
                  @click="confirmSetBest"
                  class="bg-amber-500 hover:bg-amber-600 text-white text-sm px-4 py-1.5 rounded shadow transition-colors flex items-center gap-2">
              <span>👑</span> 设为优选
          </button>
          <span v-else class="text-amber-400 font-bold flex items-center gap-2 bg-amber-900/30 px-3 py-1 rounded">
              <span>👑</span> 当前优选
          </span>
      </template>
      <template #thumb-badge="{ item }">
          <div v-if="item.is_best" class="absolute top-0 right-0 bg-amber-500 text-[8px] p-0.5 leading-none rounded-bl text-white">👑</div>
      </template>
  </PhotoViewer>
</template>

<script setup>
import { API_BASE } from '../api/base'
import { ref, onMounted, computed } from 'vue'
import PhotoViewer from '../components/PhotoViewer.vue'
import EmptyState from '../components/EmptyState.vue'
import { Sparkles } from 'lucide-vue-next'
import { toast } from '../composables/useToast'
import axios from 'axios'

const groups = ref([])
const loading = ref(true)
const loadingMore = ref(false)
const hasMore = ref(false)
const nextOffset = ref(0)
// --- Gallery State ---
const gallery = ref({
    open: false,
    currentGroup: null, // Holds the group object
    currentIndex: 0,
    currentImage: ''
})

const currentGalleryItem = computed(() => {
    if (!gallery.value.currentGroup) return {}
    return gallery.value.currentGroup.items[gallery.value.currentIndex]
})

const formatTime = (ts) =>
    new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false, year: 'numeric', month: 'long',
                                                  day: 'numeric', hour: '2-digit', minute: '2-digit' })

// ---- Cleaning: the checkboxes used to have no action attached at all ----
const cleaning = ref(false)
const groupSelected = (group) => group.items.filter(i => i.selected && !i.is_best)
const selectedCount = computed(() => groups.value.reduce((n, g) => n + groupSelected(g).length, 0))

const cleanSelected = async (onlyGroup = null) => {
    const targets = onlyGroup ? [onlyGroup] : groups.value
    const paths = targets.flatMap(g => groupSelected(g).map(i => i.file_path))
    if (!paths.length) return
    cleaning.value = true
    const snapshot = groups.value
    // Optimistic: drop the cleaned photos; a group left with one photo is
    // no longer a burst and disappears.
    const gone = new Set(paths)
    groups.value = groups.value
        .map(g => targets.includes(g) ? { ...g, items: g.items.filter(i => !gone.has(i.file_path)) } : g)
        .filter(g => g.items.length > 1)
    try {
        await axios.post(`${API_BASE}/files/trash`, { file_paths: paths })
        toast(`已将 ${paths.length} 张移入回收站`, {
            actionLabel: '撤销',
            duration: 8000,
            onAction: async () => {
                try {
                    await axios.post(`${API_BASE}/files/restore`, { file_paths: paths })
                    groups.value = snapshot
                } catch (e) {
                    toast('恢复失败，可在回收站中还原', { type: 'error' })
                }
            },
        })
    } catch (e) {
        groups.value = snapshot
        toast('清理失败', { type: 'error' })
    } finally {
        cleaning.value = false
    }
}

const setAsBest = (group, newItem) => {
    if (newItem.is_best) return
    
    // Find previous best and swap
    group.items.forEach(item => {
        if (item.is_best) {
            item.is_best = false
            item.selected = true // Mark old best for deletion
        }
    })
    
    newItem.is_best = true
    newItem.selected = false // Unmark new best
}

const confirmSetBest = () => {
    if (gallery.value.currentGroup && currentGalleryItem.value) {
        setAsBest(gallery.value.currentGroup, currentGalleryItem.value)
    }
}

const fetchBestShots = async (isLoadMore = false) => {
    if (isLoadMore) {
        loadingMore.value = true
    } else {
        loading.value = true
        groups.value = []
        nextOffset.value = 0
    }
    
    try {
        const res = await axios.get(`${API_BASE}/files/organize/best_shots`, {
            params: {
                limit: 15,
                offset_index: nextOffset.value
            }
        })
        
        const newGroups = res.data.groups.map(g => ({
            ...g,
            items: g.items.map(i => ({
                ...i,
                selected: !i.is_best // Default select non-best items
            }))
        }))
        
        if (isLoadMore) {
            groups.value = [...groups.value, ...newGroups]
        } else {
            groups.value = newGroups
        }
        
        hasMore.value = res.data.has_more
        nextOffset.value = res.data.next_offset
        
    } catch (e) {
        toast('连拍列表加载失败', { type: 'error' })
    } finally {
        loading.value = false
        loadingMore.value = false
    }
}

const loadMore = () => {
    if (!loadingMore.value && hasMore.value) {
        fetchBestShots(true)
    }
}

// --- Gallery Logic ---
const openGallery = (group, index) => {
    gallery.value.currentGroup = group
    gallery.value.currentIndex = index
    gallery.value.open = true
}

const closeGallery = () => {
    gallery.value.open = false
}

onMounted(() => {
    fetchBestShots()
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
</style>
