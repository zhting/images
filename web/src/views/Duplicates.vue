<template>
  <div class="p-6 max-w-6xl mx-auto">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold flex items-center gap-2 text-white">
        <Copy :size="24" class="text-blue-500" /> 重复照片
      </h1>
      <button
        v-if="ready && groups.length"
        @click="cleanAll"
        :disabled="cleaning"
        class="bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors">
        清理全部（每组保留一张）
      </button>
    </div>

    <!-- Backfill in progress -->
    <div v-if="!ready && !loading" class="bg-surface-raised border border-line rounded-2xl p-8 text-center">
      <Loader2 :size="36" class="text-blue-500 animate-spin mx-auto mb-4" />
      <h2 class="text-white font-medium mb-1">正在计算照片指纹…</h2>
      <p class="text-gray-500 text-sm mb-4">{{ task?.message || `剩余 ${pending} 张` }}</p>
      <div v-if="task" class="h-2 bg-line rounded-full overflow-hidden max-w-sm mx-auto">
        <div class="h-full bg-blue-500 rounded-full transition-all duration-500"
             :style="{ width: (task.progress * 100) + '%' }"></div>
      </div>
      <p class="text-gray-600 text-xs mt-4">首次使用需要为已有照片补算内容哈希，之后的新照片会在索引时自动计算。</p>
    </div>

    <div v-else-if="loading" class="text-center py-16 text-gray-400 animate-pulse">加载中…</div>

    <EmptyState v-else-if="groups.length === 0" :icon="Copy"
        title="没有发现重复照片"
        description="所有照片的内容指纹都是唯一的。新照片会在索引时自动检测。" />

    <!-- Groups -->
    <div v-else class="space-y-6">
      <p class="text-gray-500 text-sm">
        发现 {{ groups.length }} 组重复，可清理 {{ reclaimable }} 张冗余照片。每组默认保留最早的一张（勾选可更换）。
      </p>
      <div v-for="g in groups" :key="g.hash"
           class="bg-surface-raised border border-line rounded-xl p-4">
        <div class="flex items-center justify-between mb-3">
          <span class="text-gray-400 text-sm">{{ g.count }} 张相同照片</span>
          <button @click="cleanGroup(g)"
                  class="text-red-400 hover:text-red-300 text-sm">
            清理此组
          </button>
        </div>
        <div class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
          <div v-for="item in g.items" :key="item.file_path"
               class="relative cursor-pointer group"
               @click="g.keep = item.file_path">
            <img :src="thumbUrl(item.file_path)"
                 class="w-full aspect-square object-cover rounded-lg"
                 :class="keepPath(g) === item.file_path ? 'ring-2 ring-green-500' : 'opacity-70 group-hover:opacity-100'"
                 loading="lazy" />
            <div v-if="keepPath(g) === item.file_path"
                 class="absolute top-1 left-1 bg-green-600 text-white text-[10px] px-1.5 py-0.5 rounded">保留</div>
            <div class="text-[10px] text-gray-500 truncate mt-1" :title="item.file_path">
              {{ item.file_path.split('/').pop() }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import { Copy, Loader2 } from 'lucide-vue-next'
import EmptyState from '../components/EmptyState.vue'
import { toast } from '../composables/useToast'

const API_BASE = 'http://localhost:8001'
const loading = ref(true)
const ready = ref(false)
const pending = ref(0)
const task = ref(null)
const groups = ref([])
const reclaimable = ref(0)
const cleaning = ref(false)
let pollTimer = null

const thumbUrl = (p) => `${API_BASE}/files/thumbnail?path=${encodeURIComponent(p)}`
const keepPath = (g) => g.keep || g.items[0]?.file_path

const fetchDuplicates = async () => {
  try {
    const res = await axios.get(`${API_BASE}/files/organize/duplicates`)
    ready.value = res.data.ready
    if (res.data.ready) {
      stopPolling()
      groups.value = res.data.groups
      reclaimable.value = res.data.reclaimable
    } else {
      pending.value = res.data.pending
      task.value = res.data.task
      startPolling()
    }
  } catch (e) {
    toast('加载失败', { type: 'error' })
  } finally {
    loading.value = false
  }
}

const startPolling = () => {
  if (!pollTimer) pollTimer = setInterval(fetchDuplicates, 2000)
}
const stopPolling = () => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

const removePaths = async (paths) => {
  await axios.post(`${API_BASE}/files/trash`, { file_paths: paths })
}

const cleanGroup = async (g) => {
  const keep = keepPath(g)
  const drop = g.items.filter(i => i.file_path !== keep).map(i => i.file_path)
  if (!drop.length) return
  try {
    await removePaths(drop)
    groups.value = groups.value.filter(x => x !== g)
    reclaimable.value -= drop.length
    toast(`已移入回收站 ${drop.length} 张`, {
      actionLabel: '撤销',
      duration: 6000,
      onAction: async () => {
        await axios.post(`${API_BASE}/files/restore`, { file_paths: drop })
        fetchDuplicates()
      },
    })
  } catch (e) {
    toast('清理失败', { type: 'error' })
  }
}

const cleanAll = async () => {
  cleaning.value = true
  const drop = groups.value.flatMap(g =>
    g.items.filter(i => i.file_path !== keepPath(g)).map(i => i.file_path))
  try {
    await removePaths(drop)
    const cleared = drop.length
    groups.value = []
    reclaimable.value = 0
    toast(`已移入回收站 ${cleared} 张`, {
      actionLabel: '撤销',
      duration: 8000,
      onAction: async () => {
        await axios.post(`${API_BASE}/files/restore`, { file_paths: drop })
        fetchDuplicates()
      },
    })
  } catch (e) {
    toast('清理失败', { type: 'error' })
  } finally {
    cleaning.value = false
  }
}

onMounted(fetchDuplicates)
onUnmounted(stopPolling)
</script>
