<template>
  <div class="p-6 max-w-6xl mx-auto">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-white flex items-center gap-2">
        <Heart v-if="tab === 'favorites'" :size="22" class="text-red-500" />
        <Library v-else :size="22" class="text-blue-500" />
        {{ tab === 'favorites' ? '收藏' : (selectedAlbum ? selectedAlbum.name : '相册') }}
      </h1>
      <div class="flex items-center gap-2">
        <button v-if="selectedAlbum" @click="selectedAlbum = null"
                class="text-sm text-gray-400 hover:text-gray-200">← 返回</button>
        <button v-else-if="tab === 'albums'" @click="promptCreate"
                class="bg-blue-600 hover:bg-blue-500 text-white text-sm px-4 py-1.5 rounded-lg">新建相册</button>
      </div>
    </div>

    <!-- Tabs -->
    <div v-if="!selectedAlbum" class="flex gap-2 mb-6">
      <button @click="tab = 'albums'" class="px-3 py-1.5 rounded-lg text-sm border transition-colors"
              :class="tab === 'albums' ? 'border-blue-500 text-blue-400 bg-blue-500/10' : 'border-line-strong text-gray-400'">相册</button>
      <button @click="tab = 'favorites'; loadFavorites()" class="px-3 py-1.5 rounded-lg text-sm border transition-colors"
              :class="tab === 'favorites' ? 'border-blue-500 text-blue-400 bg-blue-500/10' : 'border-line-strong text-gray-400'">收藏</button>
    </div>

    <!-- Album list -->
    <template v-if="tab === 'albums' && !selectedAlbum">
      <EmptyState v-if="albums.length === 0" :icon="Library" title="还没有相册"
          description="新建相册后，可以在时光轴多选照片并加入相册。" />
      <div v-else class="grid grid-cols-2 md:grid-cols-4 gap-5">
        <div v-for="a in albums" :key="a.id" class="group cursor-pointer" @click="openAlbum(a)">
          <div class="aspect-square rounded-xl overflow-hidden bg-surface-sunken relative">
            <img v-if="a.cover" :src="thumbUrl(a.cover)" class="w-full h-full object-cover" loading="lazy" />
            <button @click.stop="removeAlbum(a)"
                    class="absolute top-2 right-2 bg-black/60 hover:bg-red-600 text-white text-xs w-6 h-6 rounded-full opacity-0 group-hover:opacity-100">✕</button>
          </div>
          <div class="mt-2 text-gray-200 text-sm truncate">{{ a.name }}</div>
          <div class="text-gray-500 text-xs">{{ a.count }} 张</div>
        </div>
      </div>
    </template>

    <!-- Photo grid (album contents or favorites) -->
    <template v-else>
      <EmptyState v-if="photos.length === 0" :icon="tab === 'favorites' ? Heart : Library"
          :title="tab === 'favorites' ? '还没有收藏' : '相册是空的'"
          :description="tab === 'favorites' ? '在查看器中按 F 或点击 ♥ 收藏照片。' : '在时光轴多选照片后加入相册。'" />
      <div v-else class="grid grid-cols-3 md:grid-cols-6 gap-1">
        <div v-for="(p, i) in photos" :key="p.file_path"
             class="aspect-square bg-surface-sunken cursor-pointer overflow-hidden"
             @click="openViewer(i)">
          <img :src="thumbUrl(p.file_path)" class="w-full h-full object-cover hover:opacity-90" loading="lazy" />
        </div>
      </div>
    </template>

    <PhotoViewer v-if="viewer.open" :items="photos" :start-index="viewer.index"
                 :api-base="API_BASE" :allow-trash="false"
                 @close="viewer.open = false" @index-change="i => viewer.index = i" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { Heart, Library } from 'lucide-vue-next'
import EmptyState from '../components/EmptyState.vue'
import PhotoViewer from '../components/PhotoViewer.vue'
import { toast } from '../composables/useToast'

const API_BASE = 'http://localhost:8001'
const tab = ref('albums')
const albums = ref([])
const photos = ref([])
const selectedAlbum = ref(null)
const viewer = ref({ open: false, index: 0 })

const thumbUrl = (p) => `${API_BASE}/files/thumbnail?path=${encodeURIComponent(p)}`
const openViewer = (i) => { viewer.value = { open: true, index: i } }

const loadAlbums = async () => {
  try { albums.value = (await axios.get(`${API_BASE}/albums`)).data } catch (e) { toast('加载失败', { type: 'error' }) }
}
const loadFavorites = async () => {
  try { photos.value = (await axios.get(`${API_BASE}/favorites`)).data } catch (e) { toast('加载失败', { type: 'error' }) }
}
const openAlbum = async (a) => {
  selectedAlbum.value = a
  photos.value = (await axios.get(`${API_BASE}/albums/${a.id}/photos`)).data
}
const promptCreate = async () => {
  const name = window.prompt('相册名称')
  if (!name || !name.trim()) return
  await axios.post(`${API_BASE}/albums`, { name: name.trim() })
  toast('相册已创建')
  loadAlbums()
}
const removeAlbum = async (a) => {
  await axios.delete(`${API_BASE}/albums/${a.id}`)
  toast(`已删除相册「${a.name}」`)
  loadAlbums()
}

onMounted(loadAlbums)
</script>
