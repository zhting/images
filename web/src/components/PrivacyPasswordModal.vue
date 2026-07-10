<template>
  <div v-if="modelValue" class="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-md transition-all duration-300">
    <div class="bg-[#1c1c1e] rounded-2xl shadow-2xl border border-white/10 w-full max-w-sm overflow-hidden flex flex-col p-6 animate-in fade-in zoom-in duration-200">
      
      <div class="flex flex-col items-center text-center gap-4">
        <div class="w-16 h-16 bg-blue-500/10 rounded-full flex items-center justify-center text-blue-500 text-3xl mb-2">
          🔒
        </div>
        
        <h3 class="text-xl font-semibold text-white">输入隐私密码</h3>
        <p class="text-sm text-gray-400">该目录内容已锁定，请输入密码以继续浏览。</p>
        
        <div class="w-full mt-4">
          <input 
            ref="passwordInput"
            v-model="password" 
            type="password" 
            placeholder="请输入密码"
            @keydown.enter="submit"
            class="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-blue-500 focus:bg-white/10 transition-all text-center text-lg tracking-widest placeholder:tracking-normal placeholder:text-sm"
          />
          <div v-if="error" class="mt-2 text-xs text-red-400 flex items-center justify-center gap-1">
            <span>⚠️</span> {{ error }}
          </div>
        </div>

        <div class="flex gap-3 w-full mt-6">
          <button @click="close" class="flex-1 px-4 py-2.5 rounded-xl border border-white/10 hover:bg-white/5 text-gray-300 transition-all font-medium">
            取消
          </button>
          <button 
            @click="submit" 
            :disabled="loading || !password"
            class="flex-1 px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:hover:bg-blue-600 text-white transition-all font-medium shadow-lg shadow-blue-900/20"
          >
            <span v-if="loading" class="inline-block animate-spin mr-1">⏳</span>
            验证并进入
          </button>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import axios from 'axios'

const props = defineProps({
  modelValue: Boolean,
  apiBase: { type: String, default: 'http://localhost:8001' }
})

const emit = defineEmits(['update:modelValue', 'success'])

const password = ref('')
const loading = ref(false)
const error = ref('')
const passwordInput = ref(null)

const close = () => {
  emit('update:modelValue', false)
  password.value = ''
  error.value = ''
}

const submit = async () => {
  if (!password.value) return
  
  loading.value = true
  error.value = ''
  
  try {
    const res = await axios.post(`${props.apiBase}/privacy/verify`, {
      password: password.value
    })
    
    if (res.data.verified) {
      // Emit the short-lived session token — the raw password never
      // leaves this component again (no more password query params).
      emit('success', res.data.session_token)
      close()
    }
  } catch (e) {
    error.value = e.response?.data?.detail || "密码错误，请重试"
    password.value = ''
    passwordInput.value?.focus()
  } finally {
    loading.value = false
  }
}

watch(() => props.modelValue, (val) => {
  if (val) {
    password.value = ''
    error.value = ''
    nextTick(() => {
      passwordInput.value?.focus()
    })
  }
})
</script>

<style scoped>
@keyframes in {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}
.animate-in {
  animation: in 0.2s ease-out;
}
</style>
