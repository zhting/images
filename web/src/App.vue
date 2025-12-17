<template>
  <div class="flex h-screen w-screen overflow-hidden">
    <!-- Sidebar -->
    <div class="w-64 bg-gray-900 text-white flex flex-col flex-shrink-0">
      <div class="p-6">
        <h1 class="text-2xl font-bold tracking-wider">VisionFind</h1>
        <p class="text-xs text-gray-400 mt-1">Local Visual Search</p>
      </div>

      <nav class="flex-1 px-2 space-y-1">
        <router-link to="/timeline" class="flex items-center px-4 py-3 rounded hover:bg-gray-800 transition-colors" exact-active-class="bg-gray-800 border-l-4 border-red-500">
          <span class="mr-3">⏳</span> 时光轴 (Timeline)
        </router-link>
        <router-link to="/settings" class="flex items-center px-4 py-3 rounded hover:bg-gray-800 transition-colors" exact-active-class="bg-gray-800 border-l-4 border-red-500">
          <span class="mr-3">⚙️</span> 设置 (Settings)
        </router-link>
        
        <div class="mt-6 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Explore
        </div>
        <router-link to="/on-this-day" class="flex items-center px-4 py-3 rounded hover:bg-gray-800 transition-colors" exact-active-class="bg-gray-800 border-l-4 border-teal-400">
          <span class="mr-3">📅</span> 那年今日
        </router-link>
        
        <div class="mt-6 px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Smart Organize
        </div>
        <router-link to="/best-shots" class="flex items-center px-4 py-3 rounded hover:bg-gray-800 transition-colors" exact-active-class="bg-gray-800 border-l-4 border-amber-500">
          <span class="mr-3">🌟</span> 相似图优选
        </router-link>
        <router-link to="/documents" class="flex items-center px-4 py-3 rounded hover:bg-gray-800 transition-colors" exact-active-class="bg-gray-800 border-l-4 border-blue-500">
          <span class="mr-3">📄</span> 文档归档
        </router-link>
         <router-link to="/places" class="flex items-center px-4 py-3 rounded hover:bg-gray-800 transition-colors" exact-active-class="bg-gray-800 border-l-4 border-green-500">
          <span class="mr-3">🌍</span> 地点 (Places)
        </router-link>
        <router-link to="/people" class="flex items-center px-4 py-3 rounded hover:bg-gray-800 transition-colors" exact-active-class="bg-gray-800 border-l-4 border-purple-500">
          <span class="mr-3">👥</span> 人物 (People)
        </router-link>
        <router-link to="/tags" class="flex items-center px-4 py-3 rounded hover:bg-gray-800 transition-colors" exact-active-class="bg-gray-800 border-l-4 border-pink-500">
          <span class="mr-3">🏷️</span> 标签 (Tags)
        </router-link>
      </nav>

      <div class="p-4 border-t border-gray-800">
        <div class="text-xs text-gray-500 mb-2">System Status</div>
        <div class="flex items-center gap-2 text-sm">
             <div class="w-2 h-2 rounded-full bg-green-500"></div> Backend Connected
        </div>
      </div>
    </div>

    <!-- Main Content -->
    <div class="flex-1 flex flex-col bg-gray-50 overflow-hidden">
      <!-- Header (Optional) -->
      
      <!-- Router View -->
      <main class="flex-1 overflow-auto p-0">
         <router-view v-slot="{ Component }">
            <keep-alive>
              <component :is="Component" />
            </keep-alive>
         </router-view>
      </main>
    </div>
  </div>
</template>

<script setup>
</script>
