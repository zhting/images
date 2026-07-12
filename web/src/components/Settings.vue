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

    <div class="bg-[#141414] rounded-lg shadow p-6 mb-6 border border-[#333]">
      <h2 class="text-2xl font-bold mb-4 flex items-center gap-2 text-white">
        <span>⚙️</span> 系统设置
      </h2>

      <!-- Model Configuration (New Tabbed Interface) -->
      <div class="mb-8 border border-[#333] rounded-lg overflow-hidden">
        <!-- Tabs -->
        <div class="flex bg-[#222] border-b border-[#333]">
            <button @click="modelTab = 'assignments'" 
                    class="px-6 py-3 text-sm font-medium transition-colors border-r border-[#333]"
                    :class="modelTab === 'assignments' ? 'bg-[#1a1a1a] text-blue-400' : 'text-gray-400 hover:text-gray-200'">
                🧩 模块配置 (Module Config)
            </button>
            <button @click="modelTab = 'sources'" 
                    class="px-6 py-3 text-sm font-medium transition-colors border-r border-[#333]"
                    :class="modelTab === 'sources' ? 'bg-[#1a1a1a] text-blue-400' : 'text-gray-400 hover:text-gray-200'">
                🔌 API 来源 (Sources)
            </button>
        </div>

        <div class="p-6 bg-[#1a1a1a]">
            <!-- Tab: Assignments -->
            <div v-if="modelTab === 'assignments'">
                <p class="text-xs text-gray-500 mb-4">为不同的功能模块指定使用的 API 来源和模型。</p>
                <div class="space-y-4">
                    <div v-for="mod in modules" :key="mod.key" class="border border-[#333] rounded p-4 bg-[#202020]">
                        <div class="mb-3">
                            <div class="font-bold text-gray-200">{{ mod.name }}</div>
                            <div class="text-xs text-gray-500">{{ mod.description }}</div>
                        </div>
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <!-- Source Select -->
                            <div>
                                <label class="block text-xs font-medium text-gray-400 mb-1">API 来源</label>
                                <select :value="getAssignment(mod.key).sourceId" 
                                        @change="updateAssignmentSource(mod.key, $event.target.value)"
                                        class="w-full bg-[#141414] border border-[#333] rounded px-3 py-2 text-sm text-gray-200 outline-none focus:border-blue-500">
                                    <option value="" disabled>选择来源</option>
                                    <option v-for="src in apiSources" :key="src.id" :value="src.id">
                                        {{ src.name }}
                                    </option>
                                </select>
                            </div>
                            <!-- Model Select -->
                            <div>
                                <label class="block text-xs font-medium text-gray-400 mb-1">模型 (Model)</label>
                                <select :value="getAssignment(mod.key).model"
                                        @change="updateAssignmentModel(mod.key, $event.target.value)"
                                        class="w-full bg-[#141414] border border-[#333] rounded px-3 py-2 text-sm text-gray-200 outline-none focus:border-blue-500">
                                    <option value="" disabled>选择模型</option>
                                    <template v-if="getSource(getAssignment(mod.key).sourceId)">
                                        <option v-for="m in getSource(getAssignment(mod.key).sourceId).models" :key="m" :value="m">
                                            {{ m }}
                                        </option>
                                    </template>
                                    <option v-else disabled>请先选择来源</option>
                                </select>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Tab: Sources -->
            <div v-if="modelTab === 'sources'">
                <p class="text-xs text-gray-500 mb-4">管理可用的模型服务提供商。添加后可在“模块配置”中使用。</p>
                <div class="space-y-6">
                    <div v-for="(src, idx) in apiSources" :key="src.id" class="border border-[#333] rounded p-4 bg-[#202020] relative group">
                        <!-- Header / Name -->
                        <div class="flex gap-4 mb-4">
                            <div class="flex-1">
                                <label class="block text-xs font-medium text-gray-400 mb-1">来源名称 (Name)</label>
                                <input v-model="src.name" type="text" class="w-full bg-[#141414] border border-[#333] rounded px-3 py-2 text-sm text-gray-200 outline-none focus:border-blue-500">
                            </div>
                            <div class="flex-1">
                                <label class="block text-xs font-medium text-gray-400 mb-1">API Key</label>
                                <input v-model="src.apiKey" type="password" placeholder="sk-..." class="w-full bg-[#141414] border border-[#333] rounded px-3 py-2 text-sm text-gray-200 outline-none focus:border-blue-500">
                            </div>
                        </div>
                        
                        <!-- Base URL (Optional/Advanced) -->
                        <div class="mb-4">
                            <label class="block text-xs font-medium text-gray-400 mb-1">API Base URL (Optional)</label>
                             <input v-model="src.apiUrl" type="text" placeholder="https://api.openai.com/v1" class="w-full bg-[#141414] border border-[#333] rounded px-3 py-2 text-sm text-gray-200 outline-none focus:border-blue-500 font-mono">
                             <p class="text-[10px] text-gray-500 mt-1">留空使用默认。反重力API请填写: http://127.0.0.1:8045/v1</p>
                        </div>

                        <!-- Model List -->
                        <div>
                            <label class="block text-xs font-medium text-gray-400 mb-2">可用模型 (Models) - 用逗号分隔或回车添加</label>
                            <div class="flex flex-wrap gap-2 mb-2 p-2 bg-[#141414] border border-[#333] rounded min-h-[40px]">
                                <span v-for="(m, mIdx) in src.models" :key="mIdx" class="bg-[#333] text-gray-200 px-2 py-1 rounded text-xs flex items-center gap-1">
                                    {{ m }}
                                    <button @click="src.models.splice(mIdx, 1)" class="hover:text-red-400">×</button>
                                </span>
                                <input 
                                    type="text" 
                                    placeholder="+ Add Model" 
                                    class="bg-transparent border-none text-xs text-gray-300 outline-none min-w-[80px]"
                                    @keydown.enter.prevent="addModelToSource(src, $event)"
                                    @blur="addModelToSource(src, $event)"
                                >
                            </div>
                        </div>

                        <!-- Delete Source -->
                        <button @click="removeSource(idx)" class="absolute top-2 right-2 text-gray-600 hover:text-red-500 transition-colors" title="删除来源">
                            ✕
                        </button>
                    </div>

                    <!-- Add New Source -->
                    <button @click="addNewSource" class="w-full py-3 border-2 border-dashed border-[#333] rounded text-gray-500 hover:border-blue-500 hover:text-blue-500 transition-colors flex items-center justify-center gap-2">
                        <span>➕</span> 添加新来源
                    </button>
                </div>
            </div>
        </div>
      </div>
        
      <!-- Index Path Setting -->
      <div class="mb-4">
           <label class="block text-sm font-medium text-gray-400 mb-1">索引数据存储位置 (Index Data Path)</label>
           <div class="flex gap-2">
               <input v-model="config.db_path" type="text" readonly class="flex-1 border border-[#333] rounded px-3 py-2 text-sm font-mono text-gray-400 bg-[#222] cursor-not-allowed">
               <button @click="changeIndexLocation" class="bg-[#333] text-gray-200 px-3 py-2 rounded text-sm hover:bg-[#444] whitespace-nowrap transition-colors">
                  📂 修改位置
               </button>
               <button @click="importIndexFile" class="bg-[#333] text-gray-200 px-3 py-2 rounded text-sm hover:bg-[#444] whitespace-nowrap transition-colors">
                  📥 导入索引
               </button>
           </div>
           <p class="text-xs text-gray-500 mt-1">⚠️ 修改及其位置后需要重启应用才能生效。如果没有选择现有的 search.db，系统会自动创建。</p>
      </div>

      <div class="flex justify-end gap-3">
           <button @click="restartApp" class="bg-[#333] text-gray-200 px-4 py-2 rounded text-sm hover:bg-[#444] flex items-center gap-2 transition-colors">
              🔄 重启应用 (Soft Restart)
           </button>
           <button @click="saveConfig" class="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 transition-colors shadow-lg">保存配置</button>
      </div>
    </div>

      <!-- Search Settings -->
      <div class="bg-[#141414] rounded-lg shadow p-6 mb-6 border border-[#333]">
        <h3 class="text-lg font-semibold mb-3 border-b border-[#333] pb-2 text-gray-200">搜索设置</h3>
        <div class="mb-4">
            <label class="block text-sm font-medium text-gray-400 mb-1">默认返回结果数量 (Top K): {{ config.top_k }}</label>
            <input v-model.number="config.top_k" type="range" min="1" max="100" class="w-full h-2 bg-[#333] rounded-lg appearance-none cursor-pointer">
            <div class="flex justify-between text-xs text-gray-500 mt-1">
                <span>1</span>
                <span>50</span>
                <span>100</span>
            </div>
        </div>
        <div class="flex justify-end">
             <button @click="saveConfig" class="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 transition-colors">保存搜索设置</button>
        </div>
      </div>

      <!-- Privacy & Security -->
      <div class="bg-[#141414] rounded-lg shadow p-6 mb-6 border border-[#333]">
        <h3 class="text-lg font-semibold mb-3 border-b border-[#333] pb-2 text-gray-200">🔒 隐私与安全</h3>
        
        <div v-if="!privacyConfig.has_password" class="mb-4">
            <p class="text-sm text-gray-400 mb-4">通过设置隐私密码，您可以锁定特定文件夹。被锁定的文件夹内容将不会出现在时光轴、搜索和各类聚合结果中。</p>
            <div class="flex flex-col gap-2">
                <div class="flex gap-2">
                    <input v-model="passwords.new" type="password" placeholder="设置新密码" class="flex-1 bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-sm text-gray-200 focus:border-blue-500 outline-none">
                    <input v-model="passwords.confirm" type="password" placeholder="确认新密码" class="flex-1 bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-sm text-gray-200 focus:border-blue-500 outline-none">
                </div>
                <button @click="updatePrivacyPassword" :disabled="!passwords.new || passwords.new !== passwords.confirm" class="w-full bg-blue-600 text-white px-6 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors">
                    {{ passwords.new !== passwords.confirm && passwords.confirm ? '密码不一致' : '设置隐私密码' }}
                </button>
            </div>
        </div>
        
        <div v-else class="space-y-6">
            <div class="flex items-center justify-between p-3 bg-blue-900/10 border border-blue-900/20 rounded-lg">
                <div class="flex items-center gap-3">
                    <span class="text-xl">🛡️</span>
                    <div>
                        <div class="text-sm font-bold text-blue-400">隐私保护已开启</div>
                        <div class="text-xs text-gray-500">已有 {{ privacyConfig.locked_folders.length }} 个文件夹被锁定</div>
                    </div>
                </div>
                <button @click="clearPrivacyPassword" class="text-xs text-red-500 hover:underline">清除密码并重置</button>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <!-- Change Password -->
                <div class="p-4 bg-[#1a1a1a] rounded border border-[#333]">
                    <h4 class="text-sm font-bold text-gray-300 mb-3">修改密码</h4>
                    <div class="space-y-3">
                        <input v-model="passwords.old" type="password" placeholder="当前密码" class="w-full bg-[#141414] border border-[#333] rounded px-3 py-1.5 text-sm text-gray-200 focus:border-blue-500 outline-none">
                        <input v-model="passwords.new" type="password" placeholder="新密码" class="w-full bg-[#141414] border border-[#333] rounded px-3 py-1.5 text-sm text-gray-200 focus:border-blue-500 outline-none">
                        <input v-model="passwords.confirm" type="password" placeholder="确认新密码" class="w-full bg-[#141414] border border-[#333] rounded px-3 py-1.5 text-sm text-gray-200 focus:border-blue-500 outline-none">
                        <button @click="updatePrivacyPassword" :disabled="!passwords.old || !passwords.new || passwords.new !== passwords.confirm" class="w-full bg-[#333] text-gray-200 py-2 rounded text-sm hover:bg-[#444] transition-colors disabled:opacity-50">
                            {{ passwords.new !== passwords.confirm && passwords.confirm ? '密码不一致' : '修改密码' }}
                        </button>
                    </div>
                </div>

                <!-- Locked Folders Info -->
                <div class="p-4 bg-[#1a1a1a] rounded border border-[#333]">
                    <h4 class="text-sm font-bold text-gray-300 mb-3">已锁定的文件夹</h4>
                    <div v-if="privacyConfig.locked_folders.length === 0" class="text-xs text-gray-500 italic">暂无锁定的文件夹</div>
                    <ul class="space-y-1 max-h-32 overflow-y-auto pr-2">
                        <li v-for="folder in privacyConfig.locked_folders" :key="folder" class="text-[11px] font-mono text-gray-400 truncate bg-[#141414] px-2 py-1 rounded">
                            {{ folder }}
                        </li>
                    </ul>
                    <p class="text-[10px] text-gray-600 mt-3">💡 您可以在“文件夹”模块中对目录进行加锁或解锁操作。</p>
                </div>
            </div>
        </div>
      </div>

      <!-- Asset Paths -->
      <div class="bg-[#141414] rounded-lg shadow p-6 mb-6 border border-[#333]">
        <h3 class="text-lg font-semibold mb-3 border-b border-[#333] pb-2 text-gray-200">照片文件夹</h3>
        
        <div class="flex gap-2 mb-4">
             <div class="flex-1">
                <input v-model="newPath" type="text" placeholder="输入本地文件夹绝对路径，或直接点击添加按钮选择" class="w-full bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-sm text-gray-200 focus:border-blue-500 outline-none">
             </div>
             <button @click="addPath" class="bg-blue-600 text-white px-6 py-2 rounded text-sm hover:bg-blue-700 whitespace-nowrap transition-colors">添加目录</button>
        </div>

        <div v-if="loadingPaths" class="text-gray-500 text-sm">加载中...</div>
        <div v-else-if="paths.length === 0" class="text-gray-500 text-sm italic">暂无配置的目录</div>
        <ul class="space-y-2">
            <li v-for="path in paths" :key="path" class="flex justify-between items-center bg-[#1a1a1a] p-2 rounded border border-[#333]">
                 <span class="text-sm font-mono truncate text-gray-300" :title="path">{{ path }}</span>
                 <button @click="removePath(path)" class="text-red-400 hover:bg-red-900/20 p-1 rounded transition-colors">✕</button>
            </li>
        </ul>
      </div>

      <!-- Index Management -->
      <div class="bg-[#141414] rounded-lg shadow p-6 mb-6 border border-[#333]">
        <h3 class="text-lg font-semibold mb-3 border-b border-[#333] pb-2 text-gray-200">扫描与索引</h3>
        <div class="mb-4 text-sm">
          <router-link to="/logs" class="text-gray-500 hover:text-gray-300 underline underline-offset-2">查看运行日志 →</router-link>
        </div>
        
        <!-- Stats -->
        <div class="grid grid-cols-2 gap-4 mb-4 text-sm text-gray-400 bg-[#1a1a1a] p-3 rounded border border-[#333]">
            <div>
                <span class="font-bold block text-gray-200">当前索引数量</span>
                <span>{{ indexState.db_count }} (照片: {{ (indexState.stats?.photo || 0) + (indexState.stats?.screenshot || 0) + (indexState.stats?.document || 0) }} / 视频: {{ indexState.stats?.video || 0 }})</span>
            </div>
            <div>
                <span class="font-bold block text-gray-200">上次更新时间</span>
                <span>{{ indexState.last_updated }}</span>
            </div>
        </div>

        <!-- Action Area -->
        <div v-if="['idle', 'scanned', 'error', 'completed', 'stopped'].includes(indexState.status)" class="space-y-4">
             
             <!-- Scan Result -->
             <div v-if="indexState.scan_result" class="bg-blue-900/20 p-4 rounded border border-blue-800/30">
                 <h4 class="font-bold text-blue-400 mb-2">扫描结果</h4>
                  <div class="flex flex-col gap-1 text-sm mb-2 text-gray-300">
                      <div class="flex gap-2 items-center">
                          <span class="font-bold text-gray-400 w-12">新增:</span>
                          <span>{{ indexState.scan_result.added }}</span>
                          <span class="text-xs text-gray-500" v-if="indexState.scan_result.added > 0">
                              (照片: {{ indexState.scan_result.added_photos }}, 视频: {{ indexState.scan_result.added_videos }})
                          </span>
                      </div>
                      <div class="flex gap-2 items-center">
                          <span class="font-bold text-gray-400 w-12">更新:</span>
                          <span>{{ indexState.scan_result.updated }}</span>
                           <span class="text-xs text-gray-500" v-if="indexState.scan_result.updated > 0">
                               (照片: {{ indexState.scan_result.updated_photos }}, 视频: {{ indexState.scan_result.updated_videos }})
                          </span>
                      </div>
                      <div class="flex gap-2 items-center">
                          <span class="font-bold text-gray-400 w-12">删除:</span>
                          <span>{{ indexState.scan_result.deleted }}</span>
                      </div>
                  </div>
                 <div class="text-xs text-gray-500 mb-3">
                     预计耗时: {{ estimateTime(indexState.scan_result.total_ops) }} (取决于硬件)
                 </div>
                 <div v-if="indexState.scan_result.total_ops === 0" class="text-sm text-gray-400 italic py-2">
                      ✨ 无变动，无需更新
                 </div>
                 <button v-else @click.prevent="runIndex(isForceScan)" type="button" class="bg-blue-600 text-white px-4 py-2 rounded shadow hover:bg-blue-700 text-sm transition-colors">
                     {{ isForceScan ? '🔥 执行全量重建' : '执行更新' }}
                 </button>
             </div>

             <!-- Main Buttons -->
             <div class="flex gap-4 items-center">
                 <button @click.prevent="startScan(false)" type="button" class="bg-[#333] text-gray-200 border border-[#444] px-4 py-2 rounded hover:bg-[#444] flex items-center gap-2 transition-colors">
                    🔍 检查变更 (Scan)
                 </button>
                 
                 <button @click.prevent="startScan(true)" type="button" class="bg-red-900/20 text-red-400 border border-red-900/30 px-4 py-2 rounded hover:bg-red-900/30 flex items-center gap-2 transition-colors">
                    ⚠️ 强制全量重建
                 </button>
             </div>
             <p v-if="indexState.status === 'error'" class="text-red-500 text-sm mt-2">错误: {{ indexState.phase }}</p>
             <p v-if="indexState.status === 'stopped'" class="text-orange-500 text-sm mt-2">⚠️ 索引已中止</p>
        </div>

        <!-- Progress Bar -->
        <div v-else class="mt-4 p-4 border border-[#333] rounded bg-[#1a1a1a]">
            <div class="stat-card bg-[#222] p-4 rounded-lg text-center mb-4">
                <div class="text-2xl font-bold text-blue-400">{{ indexState.db_count || 0 }}</div>
                <div class="text-xs text-gray-500 font-medium uppercase tracking-wide">总文件</div>
                <!-- Detailed Stats -->
                <div v-if="indexState.stats" class="mt-2 text-xs text-gray-500 flex justify-center gap-3">
                    <span title="Photos">📷 {{ (indexState.stats.photo || 0) + (indexState.stats.screenshot || 0) + (indexState.stats.document || 0) }}</span>
                    <span title="Videos">🎥 {{ indexState.stats.video || 0 }}</span>
                </div>
            </div>
             <div class="flex justify-between items-center mb-2">
                 <span class="font-bold text-gray-300">{{ indexState.phase }}</span>
                 <div class="text-sm font-mono flex items-center gap-4 text-gray-400">
                     <button @click="stopIndex" class="bg-red-600 text-white px-2 py-0.5 rounded text-xs hover:bg-red-700 transition-colors">
                        🛑 停止
                     </button>
                     <span v-if="indexState.status === 'indexing'" class="text-gray-500">
                         剩于: {{ estimatedRemainingTime }}
                     </span>
                     <span class="text-xs bg-[#333] px-2 py-0.5 rounded text-gray-400 border border-[#444]">
                        Device: {{ systemInfo?.device === 'cuda' ? 'GPU' : 'CPU' }}
                     </span>
                     <!-- Processing Counts -->
                     <span class="text-xs text-blue-400" v-if="indexState.processed_photos !== undefined">
                        Processing: 📷{{ indexState.processed_photos }} 🎥{{ indexState.processed_videos }}
                     </span>
                     <span>{{ indexState.current }} / {{ indexState.total }}</span>
                     <!-- New Breakdown -->
                     <span v-if="indexState.total > 0 && (indexState.total_photos > 0 || indexState.total_videos > 0)" class="text-xs text-gray-500">
                        (📷{{ indexState.total_photos }} 🎥{{ indexState.total_videos }})
                     </span>
                 </div>
             </div>
             
             <!-- Bar -->
             <div class="w-full bg-[#333] rounded-full h-4 overflow-hidden relative">
                 <div class="bg-blue-600 h-4 rounded-full transition-all duration-300 relative z-10" 
                      :style="{ width: percent + '%' }"></div>
             </div>
             
             <div class="text-xs text-gray-500 mt-2 truncate max-w-full flex justify-between">
                 <span>{{ indexState.current_file }}</span>
                 <span>{{ percent }}%</span>
             </div>
        </div>
      </div>
      <!-- File Browser Modal -->
      <FileBrowserModal 
          v-model="showFileBrowser" 
          :mode="fileBrowserMode"
          :api-base="API_BASE"
          @select="handleFileSelect"
      />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import axios from 'axios'
import FileBrowserModal from './FileBrowserModal.vue'

const API_BASE = 'http://localhost:8001'
const paths = ref([])
const loadingPaths = ref(true)
const newPath = ref('')
const indexing = ref(false)
const indexStatus = ref('')
const systemInfo = ref(null)
const indexStats = ref({ count: 0, last_updated: 'Unknown' })

// File Browser State
const showFileBrowser = ref(false)
const fileBrowserMode = ref('folder') // 'folder' | 'file'
const fileBrowserCallback = ref(null)

// Privacy State
const privacyConfig = ref({ has_password: false, locked_folders: [] })
const passwords = ref({ old: '', new: '', confirm: '' })

const fetchPrivacyConfig = async () => {
    try {
        const res = await axios.get(`${API_BASE}/privacy/config`)
        privacyConfig.value = res.data
    } catch (e) {
        console.error("Privacy config error", e)
    }
}

const updatePrivacyPassword = async () => {
    if (passwords.value.new !== passwords.value.confirm) {
        alert("两次输入的密码不一致")
        return
    }
    
    try {
        await axios.post(`${API_BASE}/privacy/password`, {
            old_password: passwords.value.old,
            password: passwords.value.new
        })
        alert("密码设置成功 ✅")
        passwords.value = { old: '', new: '', confirm: '' }
        fetchPrivacyConfig()
    } catch (e) {
        alert("操作失败: " + (e.response?.data?.detail || e.message))
    }
}

const clearPrivacyPassword = async () => {
    if (!confirm("确定要清除隐私密码吗？\n所有已锁定的文件夹将对所有人可见。")) return
    
    const old = prompt("请输入当前密码以确认清除:")
    if (!old) return

    try {
        await axios.post(`${API_BASE}/privacy/password`, {
            old_password: old,
            password: "" // Empty means clear
        })
        alert("隐私保护已禁用")
        fetchPrivacyConfig()
    } catch (e) {
        alert("操作失败: " + (e.response?.data?.detail || e.message))
    }
}


// Current Basic Config (Legacy + System)
const config = ref({
    top_k: 10,
    api_key: '',
    model_name: '',
    db_path: ''
})

// === New Model Config Logic ===
const modelTab = ref('assignments') // 'assignments' or 'sources'

// Modules Definition
const modules = [
    { key: "travel_prompt", name: "旅行小象 - 提示词 (Prompt)", description: "文案生成 & 画面描述 (推荐 Gemini-3/1.5)" },
    { key: "travel_image", name: "旅行小象 - 图片 (Legacy)", description: "旧版单步生成 (保留兼容)" },
    { key: "travel_integrate", name: "旅行小象 - 融合 (Step 1)", description: "第一步：将小象融入照片 (推荐 Gemini-3-Image / Nano-Banana)" },
    { key: "travel_postcard", name: "旅行小象 - 明信片 (Step 2)", description: "第二步：排版生成 (推荐 Gemini-3-Image / Flux)" },
    { key: "search_ai", name: "AI 搜图 (Search)", description: "用于 '以图搜图' 功能生成参考图" }
]

// Data Storage
const apiSources = ref([])
const moduleAssignments = ref({})

// Helper: Get Source Object by ID
const getSource = (id) => apiSources.value.find(s => s.id === id)

// Helper: Get Assignment (safe)
const getAssignment = (key) => {
    if (!moduleAssignments.value[key]) {
        moduleAssignments.value[key] = { sourceId: "", model: "" }
    }
    return moduleAssignments.value[key]
}

// Actions
const updateAssignmentSource = (key, sourceId) => {
    const a = getAssignment(key)
    a.sourceId = sourceId
    a.model = "" // Reset model when source changes
    
    // Auto-select first model if available
    const src = getSource(sourceId)
    if (src && src.models.length > 0) {
        a.model = src.models[0]
    }
}

const updateAssignmentModel = (key, model) => {
    getAssignment(key).model = model
}

const addNewSource = () => {
    const id = "src_" + Date.now().toString(36)
    apiSources.value.push({
        id,
        name: "New Source",
        apiKey: "",
        apiUrl: "",
        models: ["nano-banana", "gemini-1.5-flash"]
    })
}

const removeSource = (idx) => {
    if (confirm("确定删除此 API 来源配置吗？")) {
        apiSources.value.splice(idx, 1)
    }
}

const addModelToSource = (src, event) => {
    const val = event.target.value.trim()
    if (val && !src.models.includes(val)) {
        src.models.push(val)
    }
    event.target.value = ""
}

// === End New Model Logic ===

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
let isUnmounted = false

const pollStatus = async () => {
    if (isUnmounted) return

    // Clear existing timer if any (e.g. if called manually while timer is pending)
    if (pollTimer) {
        clearTimeout(pollTimer)
        pollTimer = null
    }

    try {
        const res = await axios.get(`${API_BASE}/index/status`)
        indexState.value = res.data
    } catch (e) {
        console.error("Poll failed", e)
    } finally {
        if (isUnmounted) return
        
        // Polling logic: only continue if status implies active work
        if (['scanning', 'indexing'].includes(indexState.value.status)) {
            // Use setTimeout instead of setInterval to ensure previous request finished
            pollTimer = setTimeout(pollStatus, 1000)
        }
    }
}


const isForceScan = ref(false)

const startScan = async (force = false) => {
    try {
        isForceScan.value = force
        // Immediate feedback
        indexState.value.status = 'scanning'
        indexState.value.phase = '正在启动扫描...'
        
        // Pass force param
        await axios.get(`${API_BASE}/index/scan?force=${force}`)
        pollStatus()
    } catch (e) {
        if (e.response && e.response.status === 400 && e.response.data.detail.includes("progress")) {
             console.log("Scan already in progress, connecting...")
             pollStatus()
        } else {
             alert("扫描启动失败: " + (e.response?.data?.detail || e.message))
             isForceScan.value = false
             indexState.value.status = 'idle'
        }
    }
}

const runIndex = async (force = false) => {
    // If running from a "Force Scan" result, we should force the index run too
    // But we don't need double confirmation if we are already in the "Result" view?
    // User flow: 
    // 1. Click "Force Rebuild" -> startScan(true)
    // 2. View Result
    // 3. Click "Execute" -> runIndex(true)
    
    // If it's a manual force run without scan (legacy path?), asking confirm is good.
    // If coming from scan result, maybe less friction?
    // Let's keep confirm if force is true, just to be safe.
    
    if (force && !confirm("⚠️ 确定要执行全量重建吗？\n这将清空旧索引并根据扫描结果重新索引。")) return

    try {
        // Immediate feedback
        indexState.value.status = 'indexing'
        indexState.value.phase = '正在启动索引...'
        
        await axios.post(`${API_BASE}/index/run`, { force: force })
        pollStatus()
        // Reset flag after start
        isForceScan.value = false 
    } catch (e) {
        if (e.response && e.response.status === 400 && e.response.data.detail.includes("progress")) {
             console.log("Index already in progress, connecting...")
             pollStatus()
             isForceScan.value = false 
        } else {
             alert("任务启动失败: " + (e.response?.data?.detail || e.message))
             indexState.value.status = 'idle' // Revert on error
        }
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
        .then(res => {
            config.value = res.data
            
            // --- Migration Logic ---
            let rawSources = config.value.api_sources || "[]"
            let rawAssignments = config.value.module_assignments || "{}"
            
            try {
                if (typeof rawSources === 'string') rawSources = JSON.parse(rawSources)
                if (typeof rawAssignments === 'string') rawAssignments = JSON.parse(rawAssignments)
            } catch (e) { rawSources=[]; rawAssignments={} }

            // If empty, migrate from legacy
            if (!Array.isArray(rawSources) || rawSources.length === 0) {
                 const legacyKey = config.value.api_key || ""
                 const legacyModel = config.value.model_name || "nano-banana"
                 
                 const defaultSource = {
                     id: "default",
                     name: "grsai.com (Default)",
                     apiKey: legacyKey,
                     models: ["nano-banana", "nano-banana-pro", "gemini-1.5-flash", "gemini-3-flash", "gemini-2.0-flash-exp"]
                 }
                 
                 // Add User Requested "Anti-Gravity" Source
                 const agSource = {
                     id: "ag_source",
                     name: "反重力",
                     apiKey: "", 
                     apiUrl: "http://127.0.0.1:8045/v1",
                     models: ["gemini-3-pro-image"]
                 }
                 
                 rawSources = [defaultSource, agSource]
                 
                 // Create Assignments
                 rawAssignments = {
                     "travel_prompt": { sourceId: "default", model: "gemini-3-flash" },
                     "travel_image": { sourceId: "default", model: "nano-banana-pro" },
                     "search_ai": { sourceId: "default", model: legacyModel }
                 }
            }
            
            apiSources.value = rawSources
            moduleAssignments.value = rawAssignments
            // -----------------------
        })
        .catch(e => console.error("Config error", e))

    axios.get(`${API_BASE}/system/info`)
        .then(res => systemInfo.value = res.data)
        .catch(e => console.error("System info error", e))

    // 3. Status
    axios.get(`${API_BASE}/index/status`)
        .then(res => indexStats.value = res.data)
        .catch(e => console.error("Index status error", e))
}

const saveConfig = async () => {
    try {
        // Sync back legacy keys for safety/fallback if needed (optional)
        // But main storage is the JSON strings
        
        await Promise.all([
            axios.post(`${API_BASE}/config`, { key: 'top_k', value: String(config.value.top_k) }),
            axios.post(`${API_BASE}/config`, { key: 'db_path', value: config.value.db_path }),
            // New Configs
            axios.post(`${API_BASE}/config`, { key: 'api_sources', value: JSON.stringify(apiSources.value) }),
            axios.post(`${API_BASE}/config`, { key: 'module_assignments', value: JSON.stringify(moduleAssignments.value) })
        ])
        alert('配置已保存 ✅')
    } catch (e) {
        alert('保存失败: ' + e.message)
    }
}

const restartApp = async () => {
    if (!confirm("确定要重新加载应用吗？\n这将重新初始化数据库和模型连接，使配置生效。")) return
    try {
        await axios.post(`${API_BASE}/system/restart`)
        alert("应用已重载 ✅\n请刷新页面以确保所有状态同步。")
        window.location.reload()
    } catch (e) {
        alert("重载失败: " + e.message)
    }
}

const addPath = async () => {
    let pathToAdd = newPath.value.trim()

    // If empty, try to pick from dialog
    if (!pathToAdd) {
        fileBrowserMode.value = 'folder'
        fileBrowserCallback.value = (path) => {
            newPath.value = path // Just set input, let user confirm add? Or auto add?
            // Auto add logic:
             axios.post(`${API_BASE}/config/paths`, { path: path })
                .then(res => {
                    paths.value = res.data.current_paths
                    newPath.value = ''
                })
                .catch(e => alert('添加失败: ' + e.message))
        }
        showFileBrowser.value = true
        return 
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



const changeIndexLocation = async () => {
    fileBrowserMode.value = 'folder'
    fileBrowserCallback.value = (path) => {
         let folder = path.replace(/\\/g, '/')
         config.value.db_path = `${folder}/search.db`
    }
    showFileBrowser.value = true
}

const importIndexFile = async () => {
    fileBrowserMode.value = 'file'
    fileBrowserCallback.value = (path) => {
         config.value.db_path = path.replace(/\\/g, '/')
    }
    showFileBrowser.value = true
}

const handleFileSelect = (path) => {
    if (fileBrowserCallback.value) {
        fileBrowserCallback.value(path)
        fileBrowserCallback.value = null
    }
}

const stopIndex = async () => {
    if (!confirm("确定要停止索引吗？")) return
    try {
        await axios.post(`${API_BASE}/index/stop`)
    } catch (e) {
        console.error(e)
    }
}

onMounted(() => {
    isUnmounted = false
    fetchConfig()
    fetchPrivacyConfig()
    pollStatus()
})

onUnmounted(() => {
    isUnmounted = true
    if (pollTimer) {
        clearTimeout(pollTimer)
        pollTimer = null
    }
})
</script>
