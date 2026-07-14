<template>
  <div class="h-full flex flex-col pt-8 px-8">
    <!-- Header -->
    <div class="flex items-end justify-between mb-8 flex-shrink-0">
      <div>
        <h2 class="text-3xl font-light tracking-tight text-content">错误日志记录</h2>
        <p class="text-gray-500 mt-2 text-sm tracking-wide">
          记录在扫描过程中因文件损坏或格式不支持而跳过的项目。您可以查看并在这里快捷跳转对应目录去移除它们。
        </p>
      </div>
      
      <div class="flex items-center gap-3">
        <button 
          v-if="logs.length > 0"
          @click="clearLogs" 
          class="flex items-center gap-2 px-4 py-2 bg-red-950/20 hover:bg-red-900/40 text-red-400 rounded-lg transition-colors text-sm font-medium border border-red-900/30"
          :disabled="clearing"
        >
          <span :class="{'animate-pulse': clearing}">🗑️</span> {{ clearing ? '正在清除...' : '清除日志' }}
        </button>

        <button 
          @click="fetchLogs" 
          class="flex items-center gap-2 px-4 py-2 bg-line hover:bg-line-strong text-gray-300 rounded-lg transition-colors text-sm font-medium border border-line-strong"
          :disabled="loading"
        >
          <span :class="{'animate-spin': loading}">🔄</span> 刷新
        </button>
      </div>
    </div>

    <!-- Content Area -->
    <div class="flex-1 overflow-hidden relative pb-8 relative group">
        
       <div v-if="loading" class="absolute inset-0 z-10 flex flex-col items-center justify-center bg-surface/80">
            <div class="w-8 h-8 rounded-full border-2 border-transparent border-t-[#666] animate-spin mb-4"></div>
            <div class="text-gray-500 text-sm tracking-widest uppercase">加载日志中...</div>
       </div>

      <!-- Empty State -->
      <div v-if="!loading && logs.length === 0" class="h-full flex flex-col items-center justify-center text-gray-500">
        <div class="text-4xl mb-4 opacity-50">✨</div>
        <h3 class="text-lg font-medium text-gray-400">暂无错误记录</h3>
        <p class="text-sm mt-2 max-w-sm text-center">
            系统状态良好。所有扫描的项目均已成功处理。未来遇到的损坏文件将会显示在这里。
        </p>
      </div>

      <!-- Logs Table -->
      <div v-else-if="!loading" class="h-full overflow-y-auto custom-scrollbar border border-line rounded-xl bg-surface-raised">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="bg-surface-sunken sticky top-0 z-10 shadow-md">
              <th class="py-3 px-6 text-xs font-semibold text-gray-400 uppercase tracking-widest whitespace-nowrap w-[180px]">发生时间</th>
              <th class="py-3 px-6 text-xs font-semibold text-gray-400 uppercase tracking-widest w-1/4">错误原因</th>
              <th class="py-3 px-6 text-xs font-semibold text-gray-400 uppercase tracking-widest">文件路径</th>
              <th class="py-3 px-6 text-xs font-semibold text-gray-400 uppercase tracking-widest text-right w-[150px]">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-line">
            <tr v-for="(log, idx) in logs" :key="idx" class="hover:bg-surface-overlay transition-colors group">
              <td class="py-3 px-6 text-sm text-gray-400 font-mono">{{ log.time }}</td>
              <td class="py-3 px-6 text-sm text-red-400/80">{{ log.reason }}</td>
              <td class="py-3 px-6 text-sm text-gray-300 font-mono truncate max-w-xs xl:max-w-md" :title="log.path">
                {{ log.path }}
              </td>
              <td class="py-3 px-6 text-right">
                <button 
                  @click="openInExplorer(log.path)"
                  class="px-3 py-1.5 bg-surface-hover hover:bg-[#444] text-white text-xs rounded transition-all flex items-center gap-2 ml-auto"
                  :class="{'!opacity-50 cursor-not-allowed': openingPaths[log.path]}"
                  :disabled="openingPaths[log.path]"
                >
                  <span class="text-[14px]">📂</span> {{ openingPaths[log.path] ? '打开中...' : '文件位置' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

    </div>
    
  </div>
</template>

<script setup>
import { API_BASE } from '../api/base'
import { ref, onMounted } from 'vue';
import axios from 'axios';

const logs = ref([]);
const loading = ref(true);
const clearing = ref(false);
const openingPaths = ref({});

const fetchLogs = async () => {
  loading.value = true;
  try {
    const res = await axios.get(`${API_BASE}/system/logs/error`);
    if (Array.isArray(res.data)) {
        logs.value = res.data;
    } else {
        console.error("API returned non-array data:", res.data);
        logs.value = [];
    }
  } catch (err) {
    console.error('Failed to fetch logs:', err);
    // Silent fail or minimal toast in real app, letting empty state handle it
  } finally {
    loading.value = false;
  }
};

const clearLogs = async () => {
    if (!confirm('确定要清除所有错误日志吗？此操作无法撤销。')) return;
    
    clearing.value = true;
    try {
        await axios.delete(`${API_BASE}/system/logs/error`);
        logs.value = [];
    } catch (err) {
        console.error('Failed to clear logs:', err);
        alert('清除日志失败。');
    } finally {
        clearing.value = false;
    }
};

const openInExplorer = async (filePath) => {
  if (openingPaths.value[filePath]) return;
  
  openingPaths.value[filePath] = true;
  try {
    await axios.post(`${API_BASE}/system/explorer`, { path: filePath });
  } catch (err) {
    console.error('Failed to open explorer:', err);
    alert('无法打开文件位置，文件可能已被移动或删除。');
  } finally {
    setTimeout(() => {
        openingPaths.value[filePath] = false;
    }, 1000);
  }
};

onMounted(() => {
  fetchLogs();
});
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: #141414;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #444;
}
</style>
