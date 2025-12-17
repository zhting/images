<template>
  <div class="max-w-4xl mx-auto">
    
    <!-- System Info Alert -->
    <div v-if="systemInfo" class="mb-6 p-4 rounded-lg flex items-center justify-between shadow-sm"
         :class="systemInfo.device === 'cuda' ? 'bg-green-50 border border-green-200 text-green-800' : 'bg-yellow-50 border border-yellow-200 text-yellow-800'">
        <div class="flex items-center gap-3">
            <span class="text-2xl">{{ systemInfo.device === 'cuda' ? '🚀' : '🐢' }}</span>
            <div>
                <div class="font-bold">{{ systemInfo.device === 'cuda' ? 'GPU 加速已开启' : 'CPU 模式运行中' }}</div>
                <div class="text-xs opacity-75">Model: {{ systemInfo.model_type }}</div>
            </div>
        </div>
        <div class="text-sm px-3 py-1 rounded bg-white/50 font-mono">
            {{ systemInfo.device.toUpperCase() }}
        </div>
    </div>

    <div class="bg-white rounded-lg shadow p-6 mb-6">
      <h2 class="text-2xl font-bold mb-4 flex items-center gap-2">
        <span>⚙️</span> 系统设置
      </h2>

      <!-- Model Configuration -->
      <div class="mb-8">
        <h3 class="text-lg font-semibold mb-3 border-b pb-2">模型设置</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
             <div>
                 <label class="block text-sm font-medium text-gray-700 mb-1">API Key</label>
                 <input v-model="config.api_key" type="password" placeholder="留空使用本地 Mock" class="w-full border border-gray-300 rounded px-3 py-2 text-sm">
             </div>
             <div>
                 <label class="block text-sm font-medium text-gray-700 mb-1">模型名称 (Model Name)</label>
                 <input v-model="config.model_name" type="text" placeholder="e.g., nano-banana" class="w-full border border-gray-300 rounded px-3 py-2 text-sm">
             </div>
        </div>
        <div class="flex justify-end">
            <button @click="saveConfig" class="bg-indigo-600 text-white px-4 py-2 rounded text-sm hover:bg-indigo-700">保存模型配置</button>
        </div>
      </div>

      <!-- Search Settings -->
      <div class="mb-8">
        <h3 class="text-lg font-semibold mb-3 border-b pb-2">搜索设置</h3>
        <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-1">默认返回结果数量 (Top K): {{ config.top_k }}</label>
            <input v-model.number="config.top_k" type="range" min="1" max="100" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer">
            <div class="flex justify-between text-xs text-gray-500 mt-1">
                <span>1</span>
                <span>50</span>
                <span>100</span>
            </div>
        </div>
        <div class="flex justify-end">
             <button @click="saveConfig" class="bg-indigo-600 text-white px-4 py-2 rounded text-sm hover:bg-indigo-700">保存搜索设置</button>
        </div>
      </div>

      <!-- Asset Paths -->
      <div class="mb-8">
        <h3 class="text-lg font-semibold mb-3 border-b pb-2">素材目录管理</h3>
        
        <div class="flex gap-2 mb-4">
             <div class="flex-1">
                <input v-model="newPath" type="text" placeholder="输入本地文件夹绝对路径，或直接点击添加按钮选择" class="w-full border border-gray-300 rounded px-3 py-2 text-sm">
             </div>
             <button @click="addPath" class="bg-blue-500 text-white px-6 py-2 rounded text-sm hover:bg-blue-600 whitespace-nowrap">添加目录</button>
        </div>

        <div v-if="loadingPaths" class="text-gray-500 text-sm">加载中...</div>
        <div v-else-if="paths.length === 0" class="text-gray-500 text-sm italic">暂无配置的目录</div>
        <ul class="space-y-2">
            <li v-for="path in paths" :key="path" class="flex justify-between items-center bg-gray-50 p-2 rounded">
                 <span class="text-sm font-mono truncate" :title="path">{{ path }}</span>
                 <button @click="removePath(path)" class="text-red-500 hover:bg-red-50 p-1 rounded">✕</button>
            </li>
        </ul>
      </div>

      <!-- Index Management -->
      <div>
        <h3 class="text-lg font-semibold mb-3 border-b pb-2">索引管理</h3>
        
        <!-- Stats -->
        <div class="grid grid-cols-2 gap-4 mb-4 text-sm text-gray-600 bg-gray-50 p-3 rounded">
            <div>
                <span class="font-bold block text-gray-800">当前索引数量</span>
                <span>{{ indexState.db_count }} 张图片</span>
            </div>
            <div>
                <span class="font-bold block text-gray-800">上次更新时间</span>
                <span>{{ indexState.last_updated }}</span>
            </div>
        </div>

        <!-- Action Area -->
        <div v-if="['idle', 'scanned', 'error', 'completed', 'stopped'].includes(indexState.status)" class="space-y-4">
             
             <!-- Scan Result -->
             <div v-if="indexState.scan_result" class="bg-blue-50 p-4 rounded border border-blue-100">
                 <h4 class="font-bold text-blue-800 mb-2">扫描结果</h4>
                 <div class="flex gap-4 text-sm mb-2">
                     <span>新增: {{ indexState.scan_result.added }}</span>
                     <span>更新: {{ indexState.scan_result.updated }}</span>
                     <span>删除: {{ indexState.scan_result.deleted }}</span>
                 </div>
                 <div class="text-xs text-gray-500 mb-3">
                     预计耗时: {{ estimateTime(indexState.scan_result.total_ops) }} (取决于硬件)
                 </div>
                 <button @click="runIndex(false)" class="bg-blue-600 text-white px-4 py-2 rounded shadow hover:bg-blue-700 text-sm">
                     执行更新
                 </button>
             </div>

             <!-- Main Buttons -->
             <div class="flex gap-4 items-center">
                 <button @click="startScan" class="bg-gray-100 text-gray-700 border px-4 py-2 rounded hover:bg-gray-200 flex items-center gap-2">
                    🔍 检查变更 (Scan)
                 </button>
                 
                 <button @click="runIndex(true)" class="bg-red-50 text-red-600 border border-red-200 px-4 py-2 rounded hover:bg-red-100 flex items-center gap-2">
                    ⚠️ 强制全量重建
                 </button>
             </div>
             <p v-if="indexState.status === 'error'" class="text-red-500 text-sm mt-2">错误: {{ indexState.phase }}</p>
             <p v-if="indexState.status === 'stopped'" class="text-orange-500 text-sm mt-2">⚠️ 索引已中止</p>
        </div>

        <!-- Progress Bar -->
        <div v-else class="mt-4 p-4 border rounded bg-gray-50">
             <div class="flex justify-between items-center mb-2">
                 <span class="font-bold text-gray-700">{{ indexState.phase }}</span>
                 <div class="text-sm font-mono flex items-center gap-4">
                     <button @click="stopIndex" class="bg-red-500 text-white px-2 py-0.5 rounded text-xs hover:bg-red-600">
                        🛑 停止
                     </button>
                     <span v-if="indexState.status === 'indexing'" class="text-gray-500">
                         剩于: {{ estimatedRemainingTime }}
                     </span>
                     <span class="text-xs bg-gray-200 px-2 py-0.5 rounded text-gray-600">
                        Device: {{ systemInfo?.device === 'cuda' ? 'GPU' : 'CPU' }}
                     </span>
                     <span>{{ indexState.current }} / {{ indexState.total }}</span>
                 </div>
             </div>
             
             <!-- Bar -->
             <div class="w-full bg-gray-200 rounded-full h-4 overflow-hidden relative">
                 <div class="bg-blue-600 h-4 rounded-full transition-all duration-300 relative z-10" 
                      :style="{ width: percent + '%' }"></div>
             </div>
             
             <div class="text-xs text-gray-500 mt-2 truncate max-w-full flex justify-between">
                 <span>{{ indexState.current_file }}</span>
                 <span>{{ percent }}%</span>
             </div>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'
const paths = ref([])
const loadingPaths = ref(true)
const newPath = ref('')
const indexing = ref(false)
const indexStatus = ref('')
const systemInfo = ref(null)
const indexStats = ref({ count: 0, last_updated: 'Unknown' })
const config = ref({
    top_k: 10,
    api_key: '',
    model_name: ''
})

const indexState = ref({
    status: 'idle',
    phase: '',
    current: 0,
    total: 0,
    current_file: '',
    db_count: 0,
    last_updated: '',
    scan_result: null
})

const percent = computed(() => {
    if (!indexState.value.total) return 0
    return Math.min(100, Math.floor((indexState.value.current / indexState.value.total) * 100))
})

const estimatedRemainingTime = computed(() => {
    if (!indexState.value.start_time || indexState.value.current < 1) return '...'
    
    const elapsed = (Date.now() / 1000) - indexState.value.start_time
    const rate = indexState.value.current / elapsed // items per second
    const remainingItems = indexState.value.total - indexState.value.current
    
    if (rate <= 0) return '...'
    
    const remainingSeconds = remainingItems / rate
    if (remainingSeconds < 60) return `${Math.ceil(remainingSeconds)}秒`
    return `${Math.ceil(remainingSeconds / 60)}分钟`
})

const estimateTime = (count) => {
    // Approx 0.8s per image for SigLIP?
    const totalSeconds = count * 0.8 
    if (totalSeconds < 60) return `${Math.ceil(totalSeconds)}秒`
    return `${Math.ceil(totalSeconds / 60)}分钟`
}

let pollTimer = null

const pollStatus = async () => {
    try {
        const res = await axios.get(`${API_BASE}/index/status`)
        indexState.value = res.data
        
        if (['scanning', 'indexing'].includes(indexState.value.status)) {
            if (!pollTimer) pollTimer = setInterval(pollStatus, 1000)
        } else {
            if (pollTimer) {
                clearInterval(pollTimer)
                pollTimer = null
            }
        }
    } catch (e) {
        console.error("Poll failed", e)
    }
}

const startScan = async () => {
    try {
        await axios.get(`${API_BASE}/index/scan`)
        pollStatus()
    } catch (e) {
        alert("扫描启动失败: " + e.message)
    }
}

const fetchConfig = () => {
    // 1. Paths (Critical, fast)
    loadingPaths.value = true
    axios.get(`${API_BASE}/config/paths`)
        .then(res => {
            paths.value = res.data
            loadingPaths.value = false
        })
        .catch(e => {
            console.error("Paths error", e)
            loadingPaths.value = false
        })

    // 2. Config & System (Less critical)
    axios.get(`${API_BASE}/config`)
        .then(res => config.value = res.data)
        .catch(e => console.error("Config error", e))

    axios.get(`${API_BASE}/system/info`)
        .then(res => systemInfo.value = res.data)
        .catch(e => console.error("System info error", e))

    // 3. Status (Might be slow)
    axios.get(`${API_BASE}/index/status`)
        .then(res => indexStats.value = res.data)
        .catch(e => console.error("Index status error", e))
}

const saveConfig = async () => {
    try {
        // Save each key individually (or batch if backend supported)
        await Promise.all([
            axios.post(`${API_BASE}/config`, { key: 'top_k', value: String(config.value.top_k) }),
            axios.post(`${API_BASE}/config`, { key: 'api_key', value: config.value.api_key }),
            axios.post(`${API_BASE}/config`, { key: 'model_name', value: config.value.model_name })
        ])
        alert('配置已保存 ✅')
    } catch (e) {
        alert('保存失败: ' + e.message)
    }
}

const addPath = async () => {
    let pathToAdd = newPath.value.trim()

    // If empty, try to pick from dialog
    if (!pathToAdd) {
        try {
            const res = await axios.post(`${API_BASE}/system/dialog/folder`)
            if (res.data.path) {
                pathToAdd = res.data.path
            } else {
                return // User cancelled dialog
            }
        } catch (e) {
            console.error(e)
            alert("无法打开文件夹选择器: " + (e.response?.data?.detail || e.message))
            return
        }
    }

    if (!pathToAdd) return

    try {
        const res = await axios.post(`${API_BASE}/config/paths`, { path: pathToAdd })
        paths.value = res.data.current_paths
        newPath.value = ''
    } catch (e) {
        alert('添加失败: ' + e.message)
    }
}

const removePath = async (path) => {
    if (!confirm(`确定要移除目录 "${path}" 吗?`)) return
    try {
        const res = await axios.delete(`${API_BASE}/config/paths`, { data: { path } })
        paths.value = res.data.current_paths
    } catch (e) {
        alert('移除失败: ' + e.message)
    }
}

const isForce = ref(false)

const runIndex = async (force = false) => {
    if (force && !confirm("⚠️ 强制全量重建将清空现有索引并重新处理所有照片。\n\n这可能需要较长时间。确定吗？")) return

    try {
        await axios.post(`${API_BASE}/index/run`, { force: force })
        pollStatus()
    } catch (e) {
        alert("任务启动失败: " + e.message)
    }
}

const stopIndex = async () => {
    if (!confirm("确定要停止索引吗？")) return
    try {
        await axios.post(`${API_BASE}/index/stop`)
        // UI will update on next poll
    } catch (e) {
        console.error(e)
    }
}

onMounted(() => {
    fetchConfig()
    pollStatus() // Initial check
})
</script>
