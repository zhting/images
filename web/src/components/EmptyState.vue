<template>
  <div class="flex flex-col items-center justify-center py-24 text-center">
    <component :is="icon" :size="44" :stroke-width="1.2" class="text-gray-600 mb-4" />
    <h3 class="text-gray-300 font-medium mb-1">{{ title }}</h3>
    <p class="text-gray-500 text-sm max-w-xs">{{ description }}</p>
  </div>
</template>

<script setup>
defineProps({
  icon: { type: [Object, Function], required: true },
  title: { type: String, required: true },
  description: { type: String, default: '照片索引完成后，这里会自动出现内容。' },
})
</script>
