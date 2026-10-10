<template>
  <router-link :to="{ path: '/frame', query: { source } }"
               class="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-full border border-line-strong text-gray-300 hover:bg-surface-hover hover:text-content"
               :title="'全屏放映' + (title ? '：' + title : '')">
    <MonitorPlay :size="15" /> 放映
  </router-link>
</template>

<script setup>
/** "放映" — open these photos in the full-screen photo frame (/frame). */
import { MonitorPlay } from 'lucide-vue-next'
defineProps({ source: { type: String, required: true }, title: { type: String, default: '' } })
</script>
