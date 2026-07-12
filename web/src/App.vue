<template>
  <!-- Global Loading Overlay -->
  <div v-if="!isAppReady" class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-[#0f0f0f] text-white">
    <div class="w-16 h-16 border-4 border-[#333] border-t-[#888] rounded-full animate-spin mb-6"></div>
    <h2 class="text-xl font-bold tracking-widest uppercase mb-2">Deep Photo</h2>
    <p class="text-sm text-gray-500 tracking-wider transition-all duration-300">{{ loadingMessage }}</p>
    <p v-if="loadingMessage.includes('后')" class="text-xs text-gray-600 mt-2">如果是首次运行，可能需要较长时间加载 AI 模型</p>
  </div>

  <div v-else class="flex h-screen w-screen overflow-hidden bg-[#0f0f0f] text-[#ececec] font-sans">
    <!-- Sidebar -->
    <div class="w-64 bg-[#141414] flex flex-col flex-shrink-0 border-r border-[#222]">
      <div class="p-8">
        <h1 class="text-xl font-bold tracking-widest text-white opacity-90 uppercase">Deep Photo</h1>
        <p class="text-[10px] text-gray-500 mt-1 uppercase tracking-widest">深象照片管理系统</p>
      </div>

      <nav class="flex-1 px-4 space-y-1 overflow-y-auto">
        <router-link to="/timeline" class="nav-item" exact-active-class="active">
          <Clock class="mr-3 opacity-70 nav-icon" :size="17" :stroke-width="1.8" /> 时光轴
        </router-link>
        <router-link to="/folders" class="nav-item" exact-active-class="active">
          <FolderOpen class="mr-3 opacity-70 nav-icon" :size="17" :stroke-width="1.8" /> 文件夹
        </router-link>
        <router-link to="/on-this-day" class="nav-item" exact-active-class="active">
          <CalendarDays class="mr-3 opacity-70 nav-icon" :size="17" :stroke-width="1.8" /> 那年今日
        </router-link>
         <router-link to="/best-shots" class="nav-item" exact-active-class="active">
          <Sparkles class="mr-3 opacity-70 nav-icon" :size="17" :stroke-width="1.8" /> 优选
        </router-link>
        
        <div class="mt-8 mb-2 px-3 text-[10px] font-bold text-gray-600 uppercase tracking-widest">
            整理
        </div>
        
        <router-link to="/places" class="nav-item" exact-active-class="active">
          <MapPin class="mr-3 opacity-70 nav-icon" :size="17" :stroke-width="1.8" /> 地点
        </router-link>
        <router-link to="/people" class="nav-item" exact-active-class="active">
          <Users class="mr-3 opacity-70 nav-icon" :size="17" :stroke-width="1.8" /> 人物
        </router-link>
        <router-link to="/tags" class="nav-item" exact-active-class="active">
          <Tags class="mr-3 opacity-70 nav-icon" :size="17" :stroke-width="1.8" /> 标签
        </router-link>
        <router-link to="/documents" class="nav-item" exact-active-class="active">
          <FileText class="mr-3 opacity-70 nav-icon" :size="17" :stroke-width="1.8" /> 文档
        </router-link>
        <router-link to="/travel" class="nav-item" exact-active-class="active">
          <Plane class="mr-3 opacity-70 nav-icon" :size="17" :stroke-width="1.8" /> 旅行小象
        </router-link>
        
        <div class="my-6 border-t border-[#222] mx-2"></div>
        
        <router-link to="/trash" class="nav-item text-gray-500 hover:text-gray-300" exact-active-class="active-trash">
          <Trash2 class="mr-3 opacity-70 nav-icon" :size="17" :stroke-width="1.8" /> 回收站
        </router-link>
        <router-link to="/logs" class="nav-item text-gray-500 hover:text-gray-300" exact-active-class="active">
          <ScrollText class="mr-3 opacity-70 nav-icon" :size="17" :stroke-width="1.8" /> 错误日志
        </router-link>
        <router-link to="/settings" class="nav-item text-gray-500 hover:text-gray-300" exact-active-class="active">
          <Settings class="mr-3 opacity-70 nav-icon" :size="17" :stroke-width="1.8" /> 设置
        </router-link>
      </nav>

      <div class="p-4 border-t border-[#222]">
        <div class="flex items-center gap-2 text-xs text-gray-600">
             <div class="w-1.5 h-1.5 rounded-full bg-green-500"></div> 在线
        </div>
      </div>
    </div>

    <!-- Main Content -->
    <div class="flex-1 flex flex-col relative overflow-hidden">
      <!-- Content Scroll Area -->
      <div id="main-scroller" class="flex-1 overflow-y-auto relative custom-scrollbar bg-[#0f0f0f]">
        <router-view></router-view>
      </div>
    </div>
    <ToastHost />
  </div>
</template>

<script setup>
import ToastHost from './components/ToastHost.vue'
import { Copy, Clock, FolderOpen, CalendarDays, Sparkles, MapPin, Users, Tags, FileText, Plane, Trash2, ScrollText, Settings } from 'lucide-vue-next'
import { ref, onMounted, onUnmounted, provide } from 'vue'
import axios from 'axios'

const isAppReady = ref(false)
const loadingMessage = ref('正在等待后端引擎启动...')
let checkInterval = null
const API_BASE = 'http://127.0.0.1:8001'

// Global Store object
const globalConfigStore = ref({
    paths: [],
    config: {},
    systemInfo: null,
    apiSources: [],
    moduleAssignments: {}
})
// Provide this to all child components so they don't have to fetch again if they just want to read
provide('globalConfigStore', globalConfigStore)

const loadSystemConfig = async () => {
    loadingMessage.value = '正在加载系统全局配置...'
    try {
        const [pathsRes, configRes, sysRes] = await Promise.all([
            axios.get(`${API_BASE}/config/paths`),
            axios.get(`${API_BASE}/config`),
            axios.get(`${API_BASE}/system/info`)
        ])
        
        globalConfigStore.value.paths = pathsRes.data
        const configData = configRes.data
        globalConfigStore.value.config = configData
        globalConfigStore.value.systemInfo = sysRes.data

        // --- Migration Logic from Settings.vue ---
        let rawSources = configData.api_sources || "[]"
        let rawAssignments = configData.module_assignments || "{}"
        
        try {
            if (typeof rawSources === 'string') rawSources = JSON.parse(rawSources)
            if (typeof rawAssignments === 'string') rawAssignments = JSON.parse(rawAssignments)
        } catch (e) { rawSources=[]; rawAssignments={} }

        // If empty, migrate from legacy
        if (!Array.isArray(rawSources) || rawSources.length === 0) {
             const legacyKey = configData.api_key || ""
             const legacyModel = configData.model_name || "nano-banana"
             
             const defaultSource = {
                 id: "default",
                 name: "grsai.com (Default)",
                 apiKey: legacyKey,
                 models: ["nano-banana", "nano-banana-pro", "gemini-1.5-flash", "gemini-3-flash", "gemini-2.0-flash-exp"]
             }
             
             const agSource = {
                 id: "ag_source",
                 name: "反重力",
                 apiKey: "", 
                 apiUrl: "http://127.0.0.1:8045/v1",
                 models: ["gemini-3-pro-image"]
             }
             
             rawSources = [defaultSource, agSource]
             
             rawAssignments = {
                 "travel_prompt": { sourceId: "default", model: "gemini-3-flash" },
                 "travel_image": { sourceId: "default", model: "nano-banana-pro" },
                 "search_ai": { sourceId: "default", model: legacyModel }
             }
        }
        
        globalConfigStore.value.apiSources = rawSources
        globalConfigStore.value.moduleAssignments = rawAssignments
        // -----------------------

        isAppReady.value = true
    } catch (err) {
        loadingMessage.value = '系统配置加载失败，正在重试...'
        console.error("Failed to load config on startup:", err)
        setTimeout(loadSystemConfig, 2000)
    }
}

const checkBackendStatus = async () => {
  try {
    const res = await axios.get(`${API_BASE}/version_check`, { timeout: 2000 })
    if (res.status === 200 && res.data.status === 'READY') {
      if (checkInterval) {
        clearInterval(checkInterval)
        checkInterval = null
      }
      // Backend is ready, now load configurations before showing the app
      await loadSystemConfig()
    }
  } catch (err) {
    // Backend not ready yet, continue polling
  }
}

onMounted(() => {
  // Check immediately
  checkBackendStatus()
  // Poll every 1.5 seconds
  checkInterval = setInterval(checkBackendStatus, 1500)
})

onUnmounted(() => {
  if (checkInterval) {
    clearInterval(checkInterval)
  }
})
</script>

<style scoped>
.nav-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  font-size: 14px;
  border-radius: 6px;
  color: #888;
  transition: all 0.2s ease;
  font-weight: 500;
}

.nav-item:hover {
  color: #ececec;
  background-color: #1a1a1a;
}

.active {
  color: #fff;
  background-color: #222;
}

/* Trash special active state */
.active-trash {
    color: #fff;
    background-color: #331111;
}

/* Scrollbar styling for main content area */
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
  background-color: #0f0f0f;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: #333;
  border-radius: 3px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background-color: #0f0f0f;
}
.nav-icon {
  display: inline-block;
  vertical-align: -3px;
  flex-shrink: 0;
}
</style>

