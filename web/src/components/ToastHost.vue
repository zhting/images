<template>
  <div class="fixed bottom-6 left-1/2 -translate-x-1/2 z-[100] flex flex-col gap-2 items-center pointer-events-none">
    <transition-group name="toast">
      <div
        v-for="t in toasts.toasts"
        :key="t.id"
        class="pointer-events-auto flex items-center gap-4 px-4 py-2.5 rounded-lg shadow-2xl border text-sm"
        :class="t.type === 'error'
          ? 'bg-red-950/95 border-red-800 text-red-100'
          : 'bg-[#1f1f1f]/95 border-[#3a3a3a] text-gray-100'"
      >
        <span>{{ t.message }}</span>
        <button
          v-if="t.actionLabel"
          @click="runAction(t)"
          class="text-blue-400 hover:text-blue-300 font-medium whitespace-nowrap"
        >{{ t.actionLabel }}</button>
        <button @click="dismiss(t.id)" class="text-gray-500 hover:text-gray-300 leading-none">✕</button>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import { useToasts, dismiss, runAction } from '../composables/useToast'
const toasts = useToasts()
</script>

<style scoped>
.toast-enter-active, .toast-leave-active { transition: all 0.18s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(8px); }
</style>
