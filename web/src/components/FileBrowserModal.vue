<template>
  <div v-if="modelValue" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm select-none">
    <div class="bg-[#191919] rounded-lg shadow-2xl border border-[#333] w-[800px] h-[550px] flex flex-col overflow-hidden text-sm text-gray-200">
      
      <!-- Top Bar: Navigation & Address -->
      <div class="flex items-center gap-2 p-2 border-b border-[#2d2d2d] bg-[#202020]">
          <!-- Nav Buttons -->
          <div class="flex gap-1">
              <button @click="goBack" :disabled="historyIndex <= 0" 
                  class="p-1 rounded hover:bg-[#333] disabled:opacity-30 disabled:hover:bg-transparent transition-colors text-gray-400">
                  ←
              </button>
              <button @click="goForward" :disabled="historyIndex >= history.length - 1"
                  class="p-1 rounded hover:bg-[#333] disabled:opacity-30 disabled:hover:bg-transparent transition-colors text-gray-400">
                  →
              </button>
              <button @click="goUp" :disabled="!currentPath"
                  class="p-1 rounded hover:bg-[#333] disabled:opacity-30 disabled:hover:bg-transparent transition-colors text-gray-400">
                  ↑
              </button>
          </div>

          <!-- Address Bar -->
          <div class="flex-1 flex px-2 py-1 bg-[#141414] border border-[#333] rounded hover:border-[#555] focus-within:border-blue-500 transition-colors">
              <span class="text-gray-500 mr-2">📁</span>
              <input 
                  v-model="currentPath" 
                  @keydown.enter="loadPath(currentPath)" 
                  class="flex-1 bg-transparent outline-none text-white text-xs font-mono"
              />
              <button @click="refresh" class="ml-2 text-gray-500 hover:text-white transition-colors">
                  ↻
              </button>
          </div>

          <!-- Search (Visual only for now) -->
          <div class="w-48 px-2 py-1 bg-[#141414] border border-[#333] rounded flex items-center text-gray-500">
              🔍 <span class="ml-2 text-xs">搜索</span>
          </div>
      </div>

      <!-- Main Body: Sidebar + File List -->
      <div class="flex-1 flex overflow-hidden">
          
          <!-- Sidebar: Drives & Favorites -->
          <div class="w-48 bg-[#1a1a1a] border-r border-[#2d2d2d] flex flex-col text-xs">
             <div class="p-2 font-bold text-gray-500 uppercase text-[10px] tracking-wider">此电脑</div>
             <div class="overflow-y-auto flex-1">
                 <div v-for="drive in drives" :key="drive" 
                      @click="loadPath(drive)"
                      :class="[
                          'px-4 py-1.5 flex items-center gap-2 cursor-pointer hover:bg-[#2a2a2a] transition-colors',
                          currentPath && currentPath.startsWith(drive) ? 'bg-[#252525] text-white' : 'text-gray-400'
                      ]"
                 >
                     <span>💾</span>
                     <span>{{ drive }}</span>
                 </div>
             </div>
          </div>

          <!-- File List (Table) -->
          <div class="flex-1 bg-[#141414] flex flex-col relative">
              
              <!-- Table Header -->
              <div class="flex px-4 py-1 text-xs text-gray-500 border-b border-[#2d2d2d] select-none">
                  <div class="flex-1 cursor-pointer hover:text-gray-300">名称</div>
                  <div class="w-32 cursor-pointer hover:text-gray-300 border-l border-[#2d2d2d] pl-2">修改日期</div>
                  <div class="w-24 cursor-pointer hover:text-gray-300 border-l border-[#2d2d2d] pl-2">类型</div>
                  <div class="w-20 cursor-pointer hover:text-gray-300 text-right border-l border-[#2d2d2d] pl-2">大小</div>
              </div>

              <!-- Content -->
              <div class="flex-1 overflow-y-auto pb-2" @click.self="selectedItem = null">
                  <div v-if="loading" class="flex justify-center items-center h-full text-gray-500 gap-2">
                       <span class="animate-spin">⏳</span>
                  </div>
                  <div v-else-if="error" class="p-8 text-center text-red-400 text-xs">
                      {{ error }}
                  </div>
                  <div v-else-if="items.length === 0" class="p-8 text-center text-gray-600 text-xs">
                      空文件夹
                  </div>
                  <template v-else>
                      <div v-for="item in items" :key="item.path"
                           @click="selectItem(item)"
                           @dblclick="openItem(item)"
                           :class="[
                               'flex px-4 py-1.5 text-xs items-center cursor-default group border-b border-transparent hover:border-[#2d2d2d]',
                               selectedItem?.path === item.path ? 'bg-[#004275] text-white' : 'text-gray-300 hover:bg-[#1f1f1f]'
                           ]"
                      >
                          <!-- Name -->
                          <div class="flex-1 flex items-center gap-2 min-w-0 pr-2">
                              <span class="text-base">{{ item.is_dir ? '📁' : '📄' }}</span>
                              <span class="truncate">{{ item.name }}</span>
                          </div>
                          <!-- Date -->
                          <div class="w-32 text-gray-500 text-[10px] pl-2 truncate group-hover:text-gray-400">
                             {{ formatDate(item.mtime) }}
                          </div>
                          <!-- Type -->
                          <div class="w-24 text-gray-500 text-[10px] pl-2 truncate group-hover:text-gray-400">
                              {{ item.type }}
                          </div>
                          <!-- Size -->
                          <div class="w-20 text-gray-500 text-[10px] pl-2 text-right truncate group-hover:text-gray-400">
                              {{ formatSize(item.size) }}
                          </div>
                      </div>
                  </template>
              </div>

          </div>
      </div>

      <!-- Footer: Selection & Buttons -->
      <div class="p-3 border-t border-[#2d2d2d] bg-[#202020] flex items-center justify-end gap-3 text-xs">
          <div class="flex-1 flex items-center gap-2">
              <span class="text-gray-500">已选:</span>
              <input :value="selectedItem ? selectedItem.name : (currentPath || '未选择')" 
                     readonly 
                     class="flex-1 bg-[#141414] border border-[#333] px-2 py-1 rounded text-gray-300" 
              />
          </div>
          <button @click="close" class="px-4 py-1.5 rounded border border-[#3d3d3d] hover:bg-[#333] text-gray-300 transition-colors">
              取消
          </button>
          <button @click="confirm" 
                  :disabled="!canConfirm"
                  class="px-4 py-1.5 rounded bg-[#0078d4] hover:bg-[#006cc1] text-white disabled:opacity-50 transition-colors shadow-sm">
              选择{{ mode === 'folder' ? '文件夹' : '文件' }}
          </button>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, computed } from 'vue'
import axios from 'axios'

const props = defineProps({
  modelValue: Boolean,
  mode: { type: String, default: 'folder' }, // 'folder' or 'file'
  initialPath: { type: String, default: '' },
  apiBase: { type: String, default: 'http://localhost:8001' }
})

const emit = defineEmits(['update:modelValue', 'select'])

// Data
const drives = ref([])
const items = ref([])
const loading = ref(false)
const error = ref('')

// Navigation State
const history = ref([])
const historyIndex = ref(-1)
const currentPath = ref('')
const selectedItem = ref(null)

// Computed
const canConfirm = computed(() => {
    if (props.mode === 'folder') {
        // Folder mode: Can confirm a selected folder OR the current open folder
        if (selectedItem.value && selectedItem.value.is_dir) return true
        if (!selectedItem.value && currentPath.value) return true
        return false
    } else {
        // File mode: Must select a file
        return selectedItem.value && !selectedItem.value.is_dir
    }
})

// === Helpers ===
const formatDate = (ts) => {
    if (!ts) return ''
    return new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false }) // Simple native format
}

const formatSize = (bytes) => {
    if (bytes === 0) return ''
    if (bytes < 1024) return bytes + ' B'
    const k = 1024
    const sizes = ['KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

// === Navigation ===
const navigateTo = (path, replace = false) => {
    if (!path) return
    
    // History Management
    if (!replace) {
        // If we are in middle of history, discard future
        if (historyIndex.value < history.length - 1) {
            history.value = history.value.slice(0, historyIndex.value + 1)
        }
        history.value.push(path)
        historyIndex.value = history.value.length - 1
    }
    
    loadPath(path)
}

const goBack = () => {
    if (historyIndex.value > 0) {
        historyIndex.value--
        loadPath(history.value[historyIndex.value])
    }
}

const goForward = () => {
    if (historyIndex.value < history.value.length - 1) {
        historyIndex.value++
        loadPath(history.value[historyIndex.value])
    }
}

const goUp = () => {
    if (!currentPath.value) return
    let p = currentPath.value.replace(/[/\\]$/, '')
    const lastSlash = Math.max(p.lastIndexOf('/'), p.lastIndexOf('\\'))
    if (lastSlash > 0) {
        p = p.substring(0, lastSlash + 1)
        navigateTo(p)
    }
}

// === API ===
const fetchDrives = async () => {
    try {
        const res = await axios.get(`${props.apiBase}/system/fs/drives`)
        drives.value = res.data.drives || []
    } catch (e) { console.error(e) }
}

const loadPath = async (path) => {
    loading.value = true
    error.value = ''
    items.value = []
    
    if (path.endsWith(':')) path += '/'
        
    try {
        const res = await axios.post(`${props.apiBase}/system/fs/list`, {
            path: path,
            only_dir: props.mode === 'folder' ? false : false 
        })
        items.value = res.data
        currentPath.value = path
        selectedItem.value = null
    } catch (e) {
        error.value = "无法访问: " + (e.response?.data?.detail || e.message)
    } finally {
        loading.value = false
    }
}

// === Actions ===
const selectItem = (item) => {
    selectedItem.value = item
}

const openItem = (item) => {
    if (item.is_dir) {
        navigateTo(item.path)
    } else if (props.mode === 'file') {
        // Double click file in file mode = select & confirm
        selectedItem.value = item
        confirm()
    }
}

const refresh = () => loadPath(currentPath.value)

const confirm = () => {
    let result = ''
    if (selectedItem.value) {
        result = selectedItem.value.path
    } else if (props.mode === 'folder' && currentPath.value) {
        result = currentPath.value
    }
    
    if (result) {
        emit('select', result)
        close()
    }
}

const close = () => {
    emit('update:modelValue', false)
}

// === Lifecycle ===
watch(() => props.modelValue, (val) => {
    if (val) {
        fetchDrives()
        // Initialize
        if (props.initialPath) {
             navigateTo(props.initialPath, true)
        } else {
             // Defer load until drives are ready? or just wait user?
             // Maybe default to first drive if no path
               // Wait for fetchDrives?
             setTimeout(() => {
                 if (drives.value.length > 0 && !currentPath.value) {
                     navigateTo(drives.value[0], true)
                 }
             }, 200)
        }
    } else {
        // Reset state?
        history.value = []
        historyIndex.value = -1
    }
})

</script>
