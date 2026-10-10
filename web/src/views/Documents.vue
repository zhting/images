<template>
  <div class="p-4 sm:p-6">
    <h1 class="text-2xl font-bold mb-6 flex items-center gap-2 text-content">
      <FileText :size="24" class="text-blue-500" /> 文档与截图
      <span v-if="total" class="text-sm font-normal text-gray-500 ml-1">{{ total }} 张</span>
    </h1>

    <div v-if="loading" class="text-center py-20 text-gray-500 animate-pulse">加载中…</div>

    <div v-else-if="loadError" class="text-center py-20">
      <p class="text-gray-400 mb-4">文档列表加载失败</p>
      <button @click="fetchDocs()" class="px-4 py-2 rounded-lg border border-line-strong text-gray-300 hover:bg-surface-hover">重试</button>
    </div>

    <EmptyState v-else-if="docs.length === 0" :icon="FileText"
        title="还没有文档"
        description="索引时会自动把截图和文档类图片归到这里。" />

    <template v-else>
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4 sm:gap-6">
        <div v-for="(doc, idx) in docs" :key="doc.file_path" class="group relative cursor-pointer" @click="openViewer(idx)">
          <div class="aspect-[3/4] rounded-lg overflow-hidden border border-line bg-surface-sunken group-hover:border-line-stronger transition-colors">
            <img :src="`${API_BASE}/files/thumbnail?path=${encodeURIComponent(doc.file_path)}`"
                 class="w-full h-full object-contain p-2" loading="lazy" decoding="async">
          </div>
          <div class="mt-2 flex items-center justify-between gap-2 text-xs text-gray-500">
            <span class="truncate" :title="doc.basename">{{ doc.basename }}</span>
            <span class="flex-shrink-0 border border-line-strong px-1.5 rounded">{{ tagLabel(doc.tag) }}</span>
          </div>
        </div>
      </div>

      <div v-if="hasMore" class="mt-12 flex justify-center pb-20">
        <button @click="fetchMore" :disabled="loadingMore"
                class="px-8 py-2.5 rounded-lg border border-line-strong text-gray-300 hover:bg-surface-hover text-sm transition-colors flex items-center gap-2 disabled:opacity-50">
          <span v-if="loadingMore" class="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></span>
          {{ loadingMore ? '加载中…' : '加载更多' }}
        </button>
      </div>
    </template>

    <PhotoViewer v-if="viewer.open" :items="docs" :start-index="viewer.index"
                 @close="closeViewer" @trash="trashFromViewer" />
  </div>
</template>

<script setup>
import { API_BASE } from '../api/base'
import EmptyState from '../components/EmptyState.vue'
import PhotoViewer from '../components/PhotoViewer.vue'
import { usePhotoViewer } from '../composables/usePhotoViewer'
import { toast } from '../composables/useToast'
import { FileText } from 'lucide-vue-next'
import { ref, onMounted } from 'vue'
import axios from 'axios'

const docs = ref([])
const total = ref(0)
const loading = ref(false)
const loadError = ref(false)
const loadingMore = ref(false)
const hasMore = ref(true)
const currentPage = ref(1)
const pageSize = 30

const { viewer, openViewer, closeViewer, trashFromViewer } =
  usePhotoViewer(docs, { onChange: (delta) => { total.value = Math.max(0, total.value + delta) } })

const TAG_LABELS = { document: '文档', screenshot: '截图' }
const tagLabel = (t) => TAG_LABELS[t] || t

const fetchDocs = async (isLoadMore = false) => {
  if (isLoadMore) loadingMore.value = true
  else { loading.value = true; loadError.value = false }
  try {
    const pageToFetch = isLoadMore ? currentPage.value + 1 : 1
    const res = await axios.get(`${API_BASE}/files/organize/documents`, {
      params: { page: pageToFetch, page_size: pageSize },
    })
    const data = res.data
    const newItems = data.items || (Array.isArray(data) ? data : [])
    if (isLoadMore) {
      docs.value.push(...newItems)
      currentPage.value = pageToFetch
    } else {
      docs.value = newItems
      currentPage.value = 1
    }
    total.value = data.total || docs.value.length
    hasMore.value = docs.value.length < total.value
  } catch (e) {
    if (isLoadMore) toast('加载更多失败', { type: 'error' })
    else loadError.value = true
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

const fetchMore = () => {
  if (!loadingMore.value && hasMore.value) fetchDocs(true)
}

onMounted(() => fetchDocs())
</script>
