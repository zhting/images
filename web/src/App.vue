<template>
  <!-- Global Loading Overlay -->
  <div v-if="!isAppReady" class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-surface text-white">
    <div class="w-16 h-16 border-4 border-line-strong border-t-[#888] rounded-full animate-spin mb-6"></div>
    <h2 class="text-xl font-bold tracking-widest uppercase mb-2">Deep Photo</h2>
    <p class="text-sm text-gray-500 tracking-wider transition-all duration-300">{{ loadingMessage }}</p>
    <p v-if="loadingMessage.includes('后')" class="text-xs text-gray-600 mt-2">如果是首次运行，可能需要较长时间加载 AI 模型</p>
  </div>

  <div v-else class="flex h-screen w-screen overflow-hidden bg-surface text-content font-sans">
    <!-- Narrow screens: the sidebar becomes a drawer behind this backdrop -->
    <div v-if="navOpen" class="fixed inset-0 z-40 bg-black/50 md:hidden" @click="navOpen = false"></div>

    <!-- Sidebar -->
    <div class="w-64 bg-surface-raised flex flex-col flex-shrink-0 border-r border-line
                fixed inset-y-0 left-0 z-50 transition-transform duration-200
                md:static md:translate-x-0"
         :class="navOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full'">
      <div class="p-8">
        <h1 class="text-xl font-bold tracking-widest text-white opacity-90 uppercase">Deep Photo</h1>
        <p class="text-[10px] text-gray-500 mt-1 uppercase tracking-widest">深象照片管理系统</p>
      </div>

      <nav class="flex-1 px-4 space-y-1 overflow-y-auto">
        <router-link to="/search" class="nav-item" active-class="active">
          <Search class="mr-3 opacity-70 nav-icon" :size="17" :stroke-width="1.8" /> 搜索
        </router-link>
        <div class="nav-section">浏览</div>
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
        <router-link to="/albums" class="nav-item" exact-active-class="active">
          <Library class="mr-3 opacity-70 nav-icon" :size="17" :stroke-width="1.8" /> 相册与收藏
        </router-link>

        <div class="nav-section">整理</div>
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
        <div class="nav-section">工具</div>
        <router-link to="/duplicates" class="nav-item" exact-active-class="active">
          <Copy class="mr-3 opacity-70 nav-icon" :size="17" :stroke-width="1.8" /> 重复照片
        </router-link>
        <router-link to="/travel" class="nav-item" exact-active-class="active">
          <Plane class="mr-3 opacity-70 nav-icon" :size="17" :stroke-width="1.8" /> 旅行小象
        </router-link>
        
        <div class="my-6 border-t border-line mx-2"></div>
        
        <router-link to="/trash" class="nav-item text-gray-500 hover:text-gray-300" exact-active-class="active-trash">
          <Trash2 class="mr-3 opacity-70 nav-icon" :size="17" :stroke-width="1.8" /> 回收站
        </router-link>
        <router-link to="/settings" class="nav-item text-gray-500 hover:text-gray-300" exact-active-class="active">
          <Settings class="mr-3 opacity-70 nav-icon" :size="17" :stroke-width="1.8" /> 设置
        </router-link>
      </nav>

      <SidebarStatus />
    </div>

    <!-- Main Content -->
    <div class="flex-1 flex flex-col relative overflow-hidden min-w-0">
      <!-- Narrow screens: menu button + current page -->
      <div class="md:hidden flex items-center gap-3 h-12 px-3 border-b border-line bg-surface-raised flex-shrink-0">
        <button @click="navOpen = true" class="p-2 -ml-1 rounded hover:bg-surface-hover" aria-label="打开导航">
          <Menu :size="20" />
        </button>
        <span class="text-sm font-medium">{{ pageTitle }}</span>
      </div>
      <!-- Content Scroll Area -->
      <div id="main-scroller" class="flex-1 overflow-y-auto relative custom-scrollbar bg-surface">
        <router-view></router-view>
      </div>
    </div>
    <ToastHost />
  </div>
</template>

<script setup>
import ToastHost from './components/ToastHost.vue'
import SidebarStatus from './components/SidebarStatus.vue'
import { Search, Library, Copy, Clock, FolderOpen, CalendarDays, Sparkles, MapPin, Users, Tags, FileText, Plane, Trash2, Settings, Menu } from 'lucide-vue-next'
import { ref, computed, watch, onMounted, onUnmounted, provide } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
// Same base as every other component. This file used to hard-code
// http://127.0.0.1:8001, so on a phone (whose 127.0.0.1 is itself) the app
// never got past the "waiting for backend" screen.
import { API_BASE } from './api/base'

const isAppReady = ref(false)
const loadingMessage = ref('正在等待后端引擎启动...')
let checkInterval = null

// Drawer navigation below the md breakpoint; closes on every navigation.
const navOpen = ref(false)
const route = useRoute()
watch(() => route.fullPath, () => { navOpen.value = false })
const PAGE_TITLES = {
  '/search': '搜索', '/timeline': '时光轴', '/folders': '文件夹', '/on-this-day': '那年今日', '/best-shots': '优选',
  '/places': '地点', '/people': '人物', '/tags': '标签', '/documents': '文档', '/travel': '旅行小象',
  '/trash': '回收站', '/settings': '设置', '/albums': '相册与收藏', '/duplicates': '重复照片', '/logs': '日志',
}
const pageTitle = computed(() => PAGE_TITLES[route.path] || 'Deep Photo')

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
.nav-section {
  font-size: 11px;
  color: #555;
  letter-spacing: 0.12em;
  padding: 14px 12px 4px;
  user-select: none;
}
</style>

