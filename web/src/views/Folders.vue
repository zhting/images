<template>
  <div class="h-full flex flex-col pt-6 px-6">
    <!-- Header -->
    <div class="flex items-end justify-between mb-6 flex-shrink-0">
      <div>
        <h2 class="text-3xl font-light tracking-tight text-content">文件夹</h2>
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
              class="group cursor-pointer bg-surface-sunken hover:bg-[#242424] border border-surface-hover hover:border-[#444] rounded-xl p-4 transition-all duration-200 relative overflow-hidden"
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
              class="relative group cursor-pointer aspect-square bg-surface-sunken overflow-hidden rounded-sm"
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
    <PhotoViewer
        v-if="gallery.open"
        :items="files"
        :start-index="gallery.currentIndex"
        :api-base="API_BASE"
        :token="sessionToken"
        :allow-trash="false"
        @close="closeGallery"
        @index-change="i => gallery.currentIndex = i"
    />
  </div>
</template>

<script setup>
import { API_BASE } from '../api/base'
import { ref, computed, onMounted, nextTick } from 'vue'
import axios from 'axios'
import PhotoViewer from '../components/PhotoViewer.vue'
import PrivacyPasswordModal from '../components/PrivacyPasswordModal.vue'

const currentPath = ref('')
const isCurrentLocked = ref(false)
const directories = ref([])
const files = ref([])
const loading = ref(true)
const error = ref('')

// Privacy State
const hasPrivacyPassword = ref(false)
const sessionToken = ref('')  // privacy session token (in-memory only)
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
const withToken = (url) => {
  return sessionToken.value ? `${url}&token=${encodeURIComponent(sessionToken.value)}` : url
}

const getThumbUrl = (path) => {
  return withToken(`${API_BASE}/files/thumbnail?path=${encodeURIComponent(path)}`)
}

const getFileUrl = (path) => {
  return withToken(`${API_BASE}/files/content?path=${encodeURIComponent(path)}`)
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
    if (sessionToken.value) {
      params.token = sessionToken.value
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
    
    // If we successfully loaded a path that was locked, our session token is valid
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

const onPasswordSuccess = (token) => {
  sessionToken.value = token
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
  gallery.value.open = true
}

const closeGallery = () => {
  gallery.value.open = false
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
