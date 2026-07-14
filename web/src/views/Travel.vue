<template>
  <div class="min-h-screen flex flex-col p-6 pb-20 overflow-y-auto bg-surface-raised">
    <div class="flex-shrink-0 mb-6">
      <h1 class="text-3xl font-light text-white flex items-center gap-3">
        🐘 旅行小象 (Beta)
        <span class="text-base text-gray-500 font-mono mt-1">Travel with Elephant</span>
      </h1>
      <p class="text-gray-400 mt-2 text-sm">此功能分两步：1. 小象入画（融合），2. 制作明信片（排版）。</p>
    </div>

    <!-- MAIN GENERATION AREA -->
    <div class="flex-col items-center justify-start w-full max-w-4xl mx-auto mb-16 min-h-[400px]">
      
      <!-- STEP 0: START -->
      <div v-if="step === 0" class="text-center mb-8 animate-fade-in">
        <div class="text-8xl mb-6 animate-bounce cursor-pointer hover:scale-110 transition-transform" @click="startIntegrate">🐘</div>
        <button 
          @click="startIntegrate"
          class="bg-blue-600 hover:bg-blue-500 text-white px-10 py-4 rounded-full text-xl font-medium transition-all shadow-lg hover:shadow-blue-500/50 flex items-center gap-2 mx-auto"
        >
          <span>🚀</span> 开始新的旅行
        </button>
      </div>

      <!-- STEP 1: PROCESSING INTEGRATION -->
      <div v-if="step === 1 && loading" class="text-center animate-pulse">
        <div class="text-6xl mb-6">📷</div>
        <h2 class="text-2xl text-white font-light mb-2">{{ statusText }}</h2>
        <p class="text-gray-500">正在寻找合适的照片并计算小象位置...</p>
      </div>

      <!-- STEP 1: REVIEW INTEGRATION -->
      <div v-if="step === 1 && !loading && integrateResult" class="w-full flex flex-col items-center animate-fade-in">
        <h2 class="text-xl text-white font-light mb-4">✨ 第一步完成：确认照片</h2>
        
        <div class="relative w-full max-w-2xl bg-black/30 rounded-lg overflow-hidden border border-gray-700 shadow-2xl mb-6 group">
             <img :src="getFileUrl(integrateResult.integrated_path)" class="w-full h-auto object-contain max-h-[60vh]" />
             <div class="absolute bottom-0 left-0 right-0 bg-black/60 p-2 text-center text-xs text-gray-300">
                预览图 (未排版)
             </div>
        </div>

        <div class="flex gap-4">
             <button 
               @click="startIntegrate"
               class="px-6 py-2 rounded-full border border-gray-600 text-gray-300 hover:bg-white/10 transition-colors flex items-center gap-2"
             >
               <span>🔄</span> 换一张 / 重试
             </button>
             <button 
               @click="viewCurrentOriginal"
               class="px-6 py-2 rounded-full border border-gray-600 text-gray-300 hover:bg-white/10 transition-colors flex items-center gap-2"
             >
               <span>🔍</span> 查看原图
             </button>
             <button 
               @click="startFinalize"
               class="bg-green-600 hover:bg-green-500 text-white px-8 py-3 rounded-full text-lg font-medium shadow-lg hover:shadow-green-500/50 flex items-center gap-2"
             >
               <span>📮</span> 生成明信片 (第二步)
             </button>
        </div>
      </div>

      <!-- STEP 2: PROCESSING FINALIZE -->
      <div v-if="step === 2 && loading" class="text-center animate-pulse">
        <div class="text-6xl mb-6">✍️</div>
        <h2 class="text-2xl text-white font-light mb-2">{{ statusText }}</h2>
        <p class="text-gray-500">正在排版、写寄语和盖邮戳...</p>
      </div>

      <!-- STEP 2: DONE -->
      <div v-if="step === 2 && !loading && finalizeResult" class="w-full flex flex-col items-center animate-fade-in">
         <!-- Postcard View is handled by the Modal logic usually, or explicitly here -->
         <!-- Note: It's added to history. We can show success and reset. -->
         <div class="text-center">
             <div class="text-6xl mb-4">🎉</div>
             <h2 class="text-2xl text-white font-bold mb-6">明信片制作完成！</h2>
             <button 
               @click="reset"
               class="bg-blue-600 hover:bg-blue-500 text-white px-8 py-3 rounded-full text-lg font-medium shadow-lg"
             >
               再来一张
             </button>
         </div>
      </div>

    </div>

    
      <!-- Postcard Gallery (Existing) -->
      <div class="w-full max-w-6xl animate-fade-in mt-12" v-if="history.length > 0">
         <div class="flex items-center justify-between mb-4 border-b border-gray-800 pb-2">
             <h3 class="text-xl text-white font-light flex items-center gap-2">
                 <span>📸</span> 我的明信片 
                 <span class="text-sm text-gray-500">({{history.length}})</span>
             </h3>
             <button 
                v-if="history.length > 0"
                @click="clearAllHistory" 
                class="text-red-400 hover:text-red-300 text-sm flex items-center gap-1 transition-colors px-3 py-1 bg-red-900/20 hover:bg-red-900/40 rounded-full"
             >
                <span>🗑️</span> 清空所有
             </button>
         </div>
         
         <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
             <div 
               v-for="item in history" 
               :key="item.filename" 
               class="aspect-[2/3] relative group rounded-lg overflow-hidden cursor-pointer border border-transparent hover:border-blue-500 transition-all shadow-md bg-gray-900"
               @click="openGalleryItem(item)"
             >
                 <img :src="getFileUrl(item.path)" class="w-full h-full object-cover" loading="lazy" />
                 
                 <div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                     <span class="text-white text-sm font-medium tracking-wide">点击查看</span>
                 </div>
                 <!-- Timestamp Badge -->
                  <div class="absolute bottom-1 right-1 bg-black/60 px-1.5 rounded text-[10px] text-gray-300 font-mono">
                      {{ formatTime(item.time) }}
                  </div>
             </div>
         </div>
      </div>
  </div>
  
    <!-- Gallery Modal (Existing) -->
    <div v-if="selectedItem" class="fixed inset-0 z-50 bg-black/95 flex items-center justify-center p-4 animate-fade-in backdrop-blur-sm" @click.self="selectedItem = null">
        <div class="relative max-w-5xl w-full max-h-[95vh] flex flex-col items-center">
             <button @click="selectedItem = null" class="absolute -top-12 right-0 text-white/50 hover:text-white text-4xl font-light transition-colors">&times;</button>
             
             <img :src="getFileUrl(selectedItem.path)" class="max-w-full max-h-[85vh] rounded shadow-2xl mb-6 border-4 border-white transform hover:scale-[1.01] transition-transform duration-500" />
             
             <div class="flex gap-4">
                  <a 
                    :href="getFileUrl(selectedItem.path)" 
                    :download="selectedItem.filename"
                    class="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2 rounded-full text-sm font-medium flex items-center gap-2 shadow-lg hover:-translate-y-1 transition-all"
                    @click.stop
                  >
                    📥 下载
                  </a>
                  <button 
                    @click.stop="viewOriginalFromGallery(selectedItem)"
                    class="bg-green-600 hover:bg-green-500 text-white px-6 py-2 rounded-full text-sm font-medium flex items-center gap-2 shadow-lg hover:-translate-y-1 transition-all"
                  >
                    🔍 查看原图
                  </button>
                  <button 
                    class="bg-red-600 hover:bg-red-500 text-white px-6 py-2 rounded-full text-sm font-medium flex items-center gap-2 shadow-lg hover:-translate-y-1 transition-all"
                    @click.stop="deleteItem(selectedItem)"
                  >
                    🗑️ 删除
                  </button>
             </div>
        </div>
    </div>

</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const step = ref(0)
const loading = ref(false)
const statusText = ref('准备出发...')

const integrateResult = ref(null)
const finalizeResult = ref(null)

const history = ref([])
const selectedItem = ref(null)

// Step Messages
const stepsIntegrate = [
    "正在寻找风景优美的照片...",
    "发现了一个好地方！",
    "小象正在挑选衣服...",
    "正在走进画面...",
    "咔嚓！拍照中..."
]
const stepsFinalize = [
    "设计师正在构思...",
    "正在排版...",
    "正在书写寄语...",
    "正在盖邮戳...",
    "明信片即将送达..."
]

let statusInterval = null

const startStatusLoop = (msgs) => {
    if (statusInterval) clearInterval(statusInterval)
    let idx = 0
    statusText.value = msgs[0]
    statusInterval = setInterval(() => {
        idx = (idx + 1) % msgs.length
        if (idx < msgs.length) statusText.value = msgs[idx]
    }, 2000)
}

const stopStatusLoop = () => {
    if (statusInterval) clearInterval(statusInterval)
    statusInterval = null
}

const reset = () => {
    step.value = 0
    integrateResult.value = null
    finalizeResult.value = null
}

// --- Step 1: Integrate ---
const startIntegrate = async () => {
    step.value = 1
    loading.value = true
    integrateResult.value = null
    startStatusLoop(stepsIntegrate)
    
    try {
        const res = await axios.post('http://localhost:8001/travel/integrate')
        if (res.data.status === 'success') {
            integrateResult.value = res.data
        } else {
            alert('融合失败: ' + (res.data.message || 'Unknown'))
            step.value = 0
        }
    } catch (e) {
        console.error(e)
        alert('API Error (Integrate): ' + (e.response?.data?.detail || e.message))
        step.value = 0
    } finally {
        stopStatusLoop()
        loading.value = false
    }
}

// --- Step 2: Finalize ---
const viewCurrentOriginal = () => {
    if (integrateResult.value && integrateResult.value.original_path) {
        window.open(getFileUrl(integrateResult.value.original_path), '_blank')
    }
}

const startFinalize = async () => {
    if (!integrateResult.value) return
    
    step.value = 2
    loading.value = true
    finalizeResult.value = null
    startStatusLoop(stepsFinalize)
    
    try {
        // Prepare request
        const payload = {
            integrated_path: integrateResult.value.integrated_path,
            original_path: integrateResult.value.original_path,
            scene: integrateResult.value.scene,
            outfit: integrateResult.value.outfit
        }
        
        const res = await axios.post('http://localhost:8001/travel/postcard_finalize', payload)
        if (res.data.status === 'success') {
            finalizeResult.value = res.data
            // Auto open it? Maybe not. Just show success.
            // Refresh history
            fetchHistory()
            // Open it automatically
            const newItem = {
                filename: res.data.saved_path.split(/[\\/]/).pop(),
                path: res.data.saved_path,
                time: Date.now() / 1000 
            }
            openGalleryItem(newItem)
        } else {
            alert('生成明信片失败: ' + (res.data.message || 'Unknown'))
            // Stay on step 2 loading? Or go back to step 1 reviewed?
            step.value = 1 // Let user retry finalize
        }
    } catch (e) {
        console.error(e)
        alert('API Error (Finalize): ' + (e.response?.data?.detail || e.message))
        step.value = 1
    } finally {
        stopStatusLoop()
        loading.value = false
    }
}


const getFileUrl = (path) => {
    if (!path) return ''
    return `http://localhost:8001/files/content?path=${encodeURIComponent(path)}`
}

const formatTime = (ts) => {
    const d = new Date(ts * 1000)
    return d.toLocaleDateString()
}

const fetchHistory = async () => {
    try {
        const res = await axios.get('http://localhost:8001/travel/history')
        history.value = res.data
    } catch (e) {
        console.error("Fetch history failed", e)
    }
}

const openGalleryItem = (item) => {
    selectedItem.value = item
}

const viewOriginalFromGallery = async (item) => {
    try {
        const res = await axios.get(`http://localhost:8001/travel/postcard/${item.filename}/metadata`)
        if (res.data && res.data.original_file_path) {
            const url = `http://localhost:8001/files/content?path=${encodeURIComponent(res.data.original_file_path)}`
            window.open(url, '_blank')
        } else {
            alert("错误: 未找到原始图片路径")
        }
    } catch (e) {
        console.error("Failed to get metadata", e)
        alert("无法获取原图信息 (Metadata missing)")
    }
}

const deleteItem = async (item) => {
    if (!confirm('确定要删除这张明信片吗？')) return
    
    try {
        await axios.delete(`http://localhost:8001/travel/postcard/${item.filename}`)
        history.value = history.value.filter(h => h.filename !== item.filename)
        if (selectedItem.value && selectedItem.value.filename === item.filename) {
            selectedItem.value = null
        }
    } catch (e) {
        alert("删除失败: " + e.message)
    }
}

const clearAllHistory = async () => {
    if (!history.value.length) return
    if (!confirm('确定要清空所有明信片吗？')) return
    try {
        await axios.delete('http://localhost:8001/travel/postcards')
        history.value = []
    } catch (e) {
        alert("清空失败: " + e.message)
    }
}

onMounted(() => {
    fetchHistory()
})

</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Caveat:wght@400;700&display=swap');

.font-handwriting {
    font-family: 'Caveat', 'Comic Sans MS', cursive, serif;
}

.animate-fade-in {
    animation: fadeIn 0.5s ease-out;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}
</style>
