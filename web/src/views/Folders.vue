<template>
  <div class="h-full flex flex-col pt-6 px-6">
    <!-- Header -->
    <div class="flex items-end justify-between mb-6 flex-shrink-0">
      <div>
        <h2 class="text-3xl font-light tracking-tight text-[#ececec]">文件夹</h2>
        <p class="text-gray-500 mt-1 text-sm tracking-wide">
          按目录结构浏览已索引的照片
        </p>
      </div>
    </div>

    <!-- Breadcrumb -->
    <div class="flex items-center gap-1 mb-5 flex-shrink-0 text-sm overflow-x-auto pb-1" v-if="currentPath">
      <button @click="loadDir('')" class="text-blue-400 hover:text-blue-300 transition-colors flex items-center gap-1 flex-shrink-0">
        <span class="text-base">🏠</span> 根目录
      </button>
      <template v-for="(crumb, idx) in breadcrumbs" :key="idx">
        <span class="text-gray-600 mx-1 flex-shrink-0">/</span>
        <button 
          v-if="idx < breadcrumbs.length - 1" 
          @click="loadDir(crumb.path)" 
          class="text-blue-400 hover:text-blue-300 transition-colors truncate max-w-[200px] flex-shrink-0"
          :title="crumb.name"
        >
          {{ crumb.name }}
        </button>
        <span v-else class="text-gray-300 truncate max-w-[200px] flex-shrink-0" :title="crumb.name">
          {{ crumb.name }}
        </span>
      </template>
      
      <!-- Prominent Lock Button for Current Folder -->
      <div v-if="hasPrivacyPassword && currentPath" class="ml-auto flex-shrink-0 pl-4">
        <button 
          @click="toggleLock()"
          class="flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all duration-200 text-xs font-medium whitespace-nowrap"
          :class="isCurrentLocked 
            ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-500 hover:bg-yellow-500/20' 
            : 'bg-white/5 border-white/10 text-gray-400 hover:bg-white/10 hover:text-white'"
        >
          <span class="text-sm">{{ isCurrentLocked ? '🔐' : '🔓' }}</span>
          {{ isCurrentLocked ? '已锁定 (点击解锁)' : '锁定此目录' }}
        </button>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto custom-scrollbar pb-8">
      
      <!-- Loading -->
      <div v-if="loading" class="flex flex-col items-center justify-center py-20">
        <div class="w-8 h-8 rounded-full border-2 border-transparent border-t-[#666] animate-spin mb-4"></div>
        <div class="text-gray-500 text-sm tracking-widest uppercase">加载中...</div>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="text-center py-20 text-red-400">
        <div class="text-4xl mb-4">⚠️</div>
        <p>{{ error }}</p>
      </div>

      <template v-else>
        <!-- Directories Grid -->
        <div v-if="directories.length > 0" class="mb-8">
          <div class="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3 px-1">
            📁 文件夹 ({{ directories.length }})
          </div>
          <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
            <div 
              v-for="dir in directories" :key="dir.path"
              @click="handleFolderClick(dir)"
              class="group cursor-pointer bg-[#1a1a1a] hover:bg-[#242424] border border-[#2a2a2a] hover:border-[#444] rounded-xl p-4 transition-all duration-200 relative overflow-hidden"
            >
              <!-- Lock Status Indicator (Keep as small visual only) -->
              <div v-if="dir.is_locked" class="absolute top-2 right-2 text-yellow-500/60 text-[10px] opacity-70">
                🔒
              </div>

              <div class="text-3xl mb-2 group-hover:scale-110 transition-transform duration-200">
                <span v-if="dir.is_locked && !sessionAuthorized">🔐</span>
                <span v-else>📁</span>
              </div>
              <div class="text-sm text-gray-200 truncate font-medium" :title="dir.name">{{ dir.name }}</div>
              <div class="text-[11px] text-gray-500 mt-1">{{ dir.count }} 张照片</div>
            </div>
          </div>
        </div>

        <!-- Photos Grid -->
        <div v-if="files.length > 0">
          <div class="text-xs font-bold text-gray-500 uppercase tracking-widest mb-3 px-1">
            🖼️ 照片 ({{ files.length }})
          </div>
          <div class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8 gap-1">
            <div 
              v-for="(item, index) in files" :key="item.file_path"
              class="relative group cursor-pointer aspect-square bg-[#1a1a1a] overflow-hidden rounded-sm"
              @click="openGallery(index)"
            >
              <img 
                :src="getThumbUrl(item.file_path)" 
                class="w-full h-full object-cover transition-opacity duration-300 hover:opacity-90"
                :loading="index < 16 ? 'eager' : 'lazy'"
                decoding="async"
              />
              <!-- Video Indicator -->
              <div v-if="item.tag === 'video'" class="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div class="bg-black/30 rounded-full p-1.5 backdrop-blur-[2px]">
                  <svg class="w-4 h-4 text-white translate-x-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-if="directories.length === 0 && files.length === 0" class="flex flex-col items-center justify-center py-20 text-gray-500">
          <div class="text-4xl mb-4 opacity-50">📂</div>
          <h3 class="text-lg font-medium text-gray-400">此目录下没有已索引的照片</h3>
          <p class="text-sm mt-2 max-w-sm text-center">
            请确认该目录已添加到资源路径，并且已完成扫描和索引。
          </p>
        </div>
      </template>
    </div>

    <!-- Password Modal -->
    <PrivacyPasswordModal 
      v-model="showPasswordModal"
      :api-base="API_BASE"
      @success="onPasswordSuccess"
    />

    <!-- Gallery Modal -->
    <div v-if="gallery.open" class="fixed inset-0 z-50 bg-black/95 flex flex-col" @keydown.esc="closeGallery" tabindex="0">
      <!-- Toolbar -->
      <div class="flex justify-between items-center p-4 text-white bg-black/50 backdrop-blur-sm z-30 absolute top-0 left-0 right-0">
        <span class="font-mono">{{ gallery.currentIndex + 1 }} / {{ files.length }}</span>
        <div class="flex items-center gap-4">
          <button @click="revealInExplorer" class="text-white hover:text-blue-400 p-2 rounded hover:bg-white/10" title="在资源管理器中显示">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path></svg>
          </button>
          <button @click="closeGallery" class="text-2xl font-bold p-2 hover:bg-white/20 rounded w-10 h-10 flex items-center justify-center">✕</button>
        </div>
      </div>
      
      <!-- Main Image/Video -->
      <div class="flex-1 flex items-center justify-center relative overflow-hidden">
        <button @click="prevImage" class="absolute left-4 z-20 text-white text-4xl p-4 hover:bg-white/10 rounded-full" v-if="gallery.currentIndex > 0">❮</button>
        
        <video v-if="isCurrentVideo" :src="gallery.currentImage" controls autoplay class="max-h-full max-w-full outline-none"></video>
        <img v-else :src="gallery.currentImage" class="max-h-full max-w-full object-contain select-none" />
        
        <button @click="nextImage" class="absolute right-4 z-20 text-white text-4xl p-4 hover:bg-white/10 rounded-full" v-if="gallery.currentIndex < files.length - 1">❯</button>
      </div>

      <!-- Thumbnails Strip -->
      <div class="h-20 bg-black/80 flex items-center gap-2 overflow-x-auto p-2" ref="thumbStrip">
        <div 
          v-for="(item, idx) in files" 
          :key="'thumb-'+idx"
          class="h-full aspect-square flex-shrink-0 cursor-pointer border-2"
          :class="idx === gallery.currentIndex ? 'border-red-500' : 'border-transparent opacity-60 hover:opacity-100'"
          @click="setGalleryIndex(idx)"
          :id="'folder-thumb-' + idx"
        >
          <img :src="getThumbUrl(item.file_path)" class="h-full w-full object-cover" />
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import axios from 'axios'
import PrivacyPasswordModal from '../components/PrivacyPasswordModal.vue'

const API_BASE = 'http://localhost:8001'

const currentPath = ref('')
const isCurrentLocked = ref(false)
const directories = ref([])
const files = ref([])
const loading = ref(true)
const error = ref('')

// Privacy State
const hasPrivacyPassword = ref(false)
const sessionPassword = ref('')
const showPasswordModal = ref(false)
const pendingPath = ref('')
const sessionAuthorized = ref(false)

const gallery = ref({
  open: false,
  currentIndex: 0,
  currentImage: ''
})

// Breadcrumb computation
const breadcrumbs = computed(() => {
  if (!currentPath.value) return []
  
  const normalized = currentPath.value.replace(/\\/g, '/')
  const parts = normalized.split('/').filter(Boolean)
  const crumbs = []
  let accumulated = ''
  
  for (let i = 0; i < parts.length; i++) {
    // Handle drive letter on Windows (e.g., "E:")
    if (i === 0 && parts[i].endsWith(':')) {
      accumulated = parts[i]
    } else {
      accumulated += '/' + parts[i]
    }
    crumbs.push({
      name: parts[i],
      path: accumulated
    })
  }
  return crumbs
})

// URL helpers
const getThumbUrl = (path) => {
  return `${API_BASE}/files/thumbnail?path=${encodeURIComponent(path)}`
}

const getFileUrl = (path) => {
  return `${API_BASE}/files/content?path=${encodeURIComponent(path)}`
}

const fetchPrivacyStatus = async () => {
  try {
    const res = await axios.get(`${API_BASE}/privacy/config`)
    hasPrivacyPassword.value = res.data.has_password
  } catch (e) {
    console.error("Failed to fetch privacy status", e)
  }
}

const loadDir = async (path) => {
  loading.value = true
  error.value = ''
  
  try {
    const params = { path: path || '' }
    if (sessionPassword.value) {
      params.password = sessionPassword.value
    }
    
    const res = await axios.get(`${API_BASE}/files/browse_dir`, { params })
    
    if (res.data.is_locked && !res.data.authorized) {
      // Access denied to this path, show password modal
      pendingPath.value = path
      showPasswordModal.value = true
      loading.value = false
      return
    }

    currentPath.value = res.data.current_path || ''
    directories.value = res.data.directories || []
    files.value = res.data.files || []
    isCurrentLocked.value = res.data.is_locked || false
    
    // If we successfully loaded a path that was locked, it means our sessionPassword is valid
    if (res.data.is_locked) {
        sessionAuthorized.value = true
    }
  } catch (err) {
    console.error('Failed to browse directory:', err)
    error.value = '加载目录失败: ' + (err.response?.data?.detail || err.message)
  } finally {
    loading.value = false
  }
}

const handleFolderClick = (dir) => {
  loadDir(dir.path)
}

const onPasswordSuccess = (pwd) => {
  sessionPassword.value = pwd
  sessionAuthorized.value = true
  if (pendingPath.value !== null) {
    loadDir(pendingPath.value)
    pendingPath.value = ''
  } else {
    refresh()
  }
}

const toggleLock = async (targetDir = null) => {
    // If no targetDir provided, we act on the current directory
    const path = targetDir ? targetDir.path : currentPath.value
    const isLocked = targetDir ? targetDir.is_locked : isCurrentLocked.value
    
    if (!path) return

    try {
        if (isLocked) {
            // Using our new endpoints: /privacy/unlock if currently locked
            await axios.post(`${API_BASE}/privacy/unlock`, { path: path })
        } else {
            await axios.post(`${API_BASE}/privacy/lock`, { path: path })
        }
        
        // Correct way to refresh for current toggle: reloadDir(currentPath.value) 
        // to get the new isCurrentLocked state from server.
        loadDir(currentPath.value)
    } catch (e) {
        alert("操作失败: " + (e.response?.data?.detail || e.message))
    }
}

const refresh = () => loadDir(currentPath.value)

// Gallery Logic
const isCurrentVideo = computed(() => {
  const item = files.value[gallery.value.currentIndex]
  return item && item.tag === 'video'
})

const openGallery = (index) => {
  gallery.value.currentIndex = index
  const item = files.value[index]
  if (item) gallery.value.currentImage = getFileUrl(item.file_path)
  gallery.value.open = true
  document.body.style.overflow = 'hidden'
  window.addEventListener('keydown', handleKey)
  nextTick(() => scrollToThumb())
}

const closeGallery = () => {
  gallery.value.open = false
  document.body.style.overflow = ''
  window.removeEventListener('keydown', handleKey)
}

const updateImage = () => {
  const item = files.value[gallery.value.currentIndex]
  if (item) {
    gallery.value.currentImage = getFileUrl(item.file_path)
    scrollToThumb()
  }
}

const prevImage = () => {
  if (gallery.value.currentIndex > 0) {
    gallery.value.currentIndex--
    updateImage()
  }
}

const nextImage = () => {
  if (gallery.value.currentIndex < files.value.length - 1) {
    gallery.value.currentIndex++
    updateImage()
  }
}

const setGalleryIndex = (idx) => {
  gallery.value.currentIndex = idx
  updateImage()
}

const handleKey = (e) => {
  if (e.key === 'ArrowLeft') prevImage()
  if (e.key === 'ArrowRight') nextImage()
  if (e.key === 'Escape') closeGallery()
}

const revealInExplorer = async () => {
  const item = files.value[gallery.value.currentIndex]
  if (!item) return
  try {
    await axios.post(`${API_BASE}/system/explorer`, { path: item.file_path })
  } catch (e) {
    console.error("Failed to reveal in explorer", e)
  }
}

// Thumb scroll
const thumbStrip = ref(null)
const scrollToThumb = () => {
  nextTick(() => {
    const el = document.getElementById('folder-thumb-' + gallery.value.currentIndex)
    if (el && thumbStrip.value) {
      el.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
    }
  })
}

// Initial Load
onMounted(() => {
  loadDir('')
  fetchPrivacyStatus()
})
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: #0f0f0f;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #444;
}
</style>
