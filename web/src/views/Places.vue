<template>
  <div class="h-full flex flex-col bg-gray-900" :class="{ 'fixed inset-0 z-50': isFullscreen }">
    <!-- Header / Tab Bar -->
    <div v-if="!isFullscreen" class="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center justify-between shadow-sm z-[2000] relative">
      <div class="flex items-center gap-4">
        <template v-if="selectedPlace">
          <button @click="selectedPlace = null" class="text-gray-300 hover:text-white flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clip-rule="evenodd" />
            </svg>
            返回: {{ selectedPlace.name }}
          </button>
          <span class="text-sm text-gray-400 bg-gray-800 px-2 py-1 rounded-full">
            {{ photos.length }} photos
          </span>
        </template>
        <template v-else>
          <!-- Tabs -->
          <nav class="flex space-x-1 border border-gray-700 rounded-lg p-1 bg-gray-800/50">
            <button v-for="tab in tabs" :key="tab.id"
              @click="switchView(tab.id)" 
              class="px-4 py-2 rounded-md text-sm font-medium transition-all flex items-center gap-2"
              :class="viewMode === tab.id ? 'bg-gray-700 text-white shadow' : 'text-gray-400 hover:text-gray-200'"
            >
              <span>{{ tab.icon }}</span> {{ tab.label }}
            </button>
          </nav>
        </template>
      </div>

      <!-- Fullscreen toggle -->
      <button @click="toggleFullscreen" class="text-gray-400 hover:text-white p-2 rounded-lg hover:bg-gray-800 transition-colors">
        <svg v-if="!isFullscreen" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
        </svg>
        <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-hidden relative">
        <!-- Detail View -->
        <div v-if="selectedPlace" class="absolute inset-0 z-[2000] bg-gray-900 flex flex-col overflow-hidden animate-fade-in shadow-2xl">
            <div class="flex items-center justify-between p-4 bg-gray-950/80 border-b border-gray-800">
                <div class="flex items-center gap-5">
                    <button @click="selectedPlace = null" class="p-2.5 bg-gray-800 hover:bg-gray-700 rounded-2xl transition-all text-white border border-gray-700">
                         <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7 7-7" /></svg>
                    </button>
                    <div>
                         <h2 class="text-xl font-bold text-white">{{ selectedPlace?.name }}</h2>
                         <div class="text-[10px] font-bold text-blue-400 mt-1 uppercase tracking-widest">
                             {{ loading ? '同步中...' : `${photos.length} 媒体` }}
                         </div>
                    </div>
                </div>
            </div>
            <div class="flex-1 overflow-y-auto p-4 custom-scrollbar bg-[#0a0a0a]">
                <div v-if="loading" class="grid grid-cols-2 sm:grid-cols-6 gap-3">
                    <div v-for="i in 18" :key="i" class="aspect-square bg-gray-900 rounded-xl pulse-glow"></div>
                </div>
                <div v-else class="grid grid-cols-2 sm:grid-cols-6 gap-3">
                    <div v-for="(photo, idx) in photos" :key="photo.file_path" class="relative group aspect-square bg-gray-900 rounded-xl overflow-hidden animate-fade-in cursor-pointer" @click="openGallery(photos, idx)">
                        <img loading="lazy" :src="`${API_BASE}/files/thumbnail?path=${encodeURIComponent(photo.file_path)}`" class="w-full h-full object-cover group-hover:scale-105 transition-transform" />
                        <!-- Video Indicator -->
                        <div v-if="photo.tag === 'video'" class="absolute inset-0 flex items-center justify-center pointer-events-none">
                            <div class="bg-black/30 rounded-full p-1.5 backdrop-blur-[2px]">
                                <svg class="w-4 h-4 text-white translate-x-0.5" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Main Views (Always in DOM to cache state) -->
        <div v-show="!selectedPlace" class="w-full h-full flex">
            <!-- World Map View -->
            <div v-show="viewMode === 'world'" class="flex-1 relative">
                <div ref="mapContainer" class="w-full h-full bg-gray-900"></div>
                <!-- World Map Loading Overlay -->
                <div v-if="loading && !selectedPlace" class="absolute inset-0 flex flex-col items-center justify-center bg-black/40 backdrop-blur-sm z-[2500]">
                     <div class="bg-gray-900/90 rounded-3xl p-8 flex flex-col items-center border border-gray-700 shadow-2xl">
                         <div class="w-12 h-12 border-4 border-gray-700 border-t-blue-500 rounded-full animate-spin mb-4"></div>
                         <div class="text-[10px] font-bold text-blue-400 uppercase tracking-widest">Loading Map data...</div>
                     </div>
                </div>
                <div v-if="!loading && !hasMapData" class="absolute inset-0 flex items-center justify-center pointer-events-none">
                     <div class="bg-gray-800 p-6 rounded-xl shadow-lg border border-gray-700 text-center animate-fade-in pointer-events-auto">
                        <p class="text-gray-400">地图暂无数据 (No GPS data)</p>
                     </div>
                </div>
            </div>
            <!-- China Map View -->
            <div v-if="viewMode === 'china'" class="w-full h-full bg-gray-800">
                <ChinaMap :places="places" :wishlist="chinaWishlist" @place-click="handleChinaMapPlaceClick" />
            </div>
            <!-- List View -->
            <div v-show="viewMode === 'list'" class="h-full w-full overflow-y-auto p-6 bg-gray-900">
                 <div class="max-w-xl mx-auto mb-8">
                    <input v-model="searchQuery" type="search" placeholder="搜索城市或地点..." class="w-full bg-gray-800 border border-gray-700 text-white px-4 py-2.5 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 shadow-lg" />
                 </div>
                 <div v-if="!loading && paginatedPlaces.length === 0" class="flex flex-col items-center justify-center py-20 text-gray-400">
                     <div class="text-6xl mb-4 text-gray-700 opacity-50">📍</div>
                     <p class="font-medium text-lg text-gray-300">暂无地点数据</p>
                     <p class="text-sm mt-2 opacity-50">尝试搜索其他城市，或等待照片定位索引完成</p>
                 </div>
                 <div v-else class="grid grid-cols-2 sm:grid-cols-5 gap-6">
                    <div v-for="place in paginatedPlaces" :key="place.name" @click="selectPlace(place)" class="group bg-gray-800 rounded-2xl overflow-hidden border border-gray-700 hover:border-blue-500/50 transition-all cursor-pointer">
                        <div class="aspect-square relative overflow-hidden">
                            <img :src="`${API_BASE}/files/thumbnail?path=${encodeURIComponent(place.cover.file_path)}`" class="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
                            <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent"></div>
                            <div class="absolute bottom-3 left-3 text-white">
                                 <div class="font-bold">{{ place.name }}</div>
                                 <div class="text-[10px] opacity-70">{{ place.count }} photos</div>
                            </div>
                        </div>
                    </div>
                </div>
                <!-- Pagination -->
                <div v-if="totalPages > 1" class="mt-8 flex justify-center gap-4 text-gray-400">
                   <button @click="currentPage--" :disabled="currentPage === 1" class="px-4 py-2 bg-gray-800 rounded-lg border border-gray-700 disabled:opacity-30">Prev</button>
                   <span class="flex items-center">{{ currentPage }} / {{ totalPages }}</span>
                   <button @click="currentPage++" :disabled="currentPage === totalPages" class="px-4 py-2 bg-gray-800 rounded-lg border border-gray-700 disabled:opacity-30">Next</button>
                </div>
            </div>
            <!-- Wishlist View -->
            <div v-show="viewMode === 'wishlist'" class="h-full w-full overflow-y-auto p-6 bg-gray-900 scroll-smooth">
                <div class="max-w-4xl mx-auto">
                    <div class="flex items-center justify-between mb-4">
                        <h2 class="text-2xl font-bold text-white">⭐ 打卡愿望清单</h2>
                        <!-- Scan button removed as requested -->
                    </div>

                    <!-- Sub Tabs -->
                    <div class="flex gap-2 mb-8 bg-gray-800/40 p-1 rounded-xl w-fit border border-gray-700/30">
                        <button v-for="st in [
                            { id: 'all', label: '愿望单', icon: '📝' },
                            { id: 'visited', label: '已打卡', icon: '✅' },
                            { id: 'unvisited', label: '未打卡', icon: '📍' }
                        ]" :key="st.id" 
                        @click="wishlistSubTab = st.id"
                        class="px-5 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2"
                        :class="wishlistSubTab === st.id ? 'bg-gray-700 text-white shadow-lg' : 'text-gray-400 hover:text-gray-200'"
                        >
                            <span>{{ st.icon }}</span> {{ st.label }}
                        </button>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                        <!-- World Wishlist -->
                        <div class="bg-gray-800/80 backdrop-blur-md rounded-2xl p-6 border border-gray-700/50 shadow-xl">
                           <h3 class="text-xl font-bold text-white mb-6 flex items-center gap-3">
                               <span class="p-2 bg-blue-500/20 rounded-lg text-blue-400">🌍</span> 
                               国际视野
                           </h3>
                           <draggable 
                             v-model="paginatedWorldWishlist" 
                             class="space-y-3" 
                             handle=".drag-handle"
                             item-key="name"
                             :disabled="wishlistSubTab !== 'all'"
                           >
                              <template #item="{element: w}">
                                <div class="group flex justify-between items-center bg-gray-900/60 p-2.5 rounded-xl border transition-all duration-300"
                                     :class="visitedCities.has(w.name) ? 'border-green-500/30 bg-green-500/5' : 'border-gray-700 hover:border-blue-500/30'"
                                >
                                   <div class="flex items-center gap-4 cursor-pointer flex-1" @click="visitedCities.has(w.name) && selectPlaceByName(w.name)">
                                      <div v-if="wishlistSubTab === 'all'" class="drag-handle p-1 text-gray-600 hover:text-gray-400 cursor-grab active:cursor-grabbing">
                                         <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9h8M8 15h8"></path></svg>
                                      </div>
                                      <span class="text-2xl">{{ w.flag || '🌍' }}</span>
                                      <div>
                                          <div class="text-gray-100 font-medium group-hover:text-white transition-colors flex items-center gap-2">
                                            {{ w.name }}
                                            <span v-if="w.country" class="text-[10px] bg-gray-700/50 text-gray-400 px-1 py-0.5 rounded">{{ w.country }}</span>
                                            <span v-if="popularCities.includes(w.name)" class="text-[9px] bg-amber-500/20 text-amber-500 px-1.5 py-0.5 rounded uppercase font-bold">Hot</span>
                                          </div>
                                          <div v-if="visitedCities.has(w.name) && wishlistSubTab === 'all'" class="text-[10px] text-green-400 font-bold uppercase tracking-wider mt-0.5">✅ 已打卡</div>
                                          <div v-else-if="!visitedCities.has(w.name) && wishlistSubTab === 'all'" class="text-[10px] text-gray-500 font-bold uppercase tracking-wider mt-0.5">⭐ 计划中</div>
                                          <div v-else-if="wishlistSubTab === 'unvisited' && hasInWorldWishlist(w.name)" class="text-[10px] text-amber-500 font-bold uppercase tracking-wider mt-0.5">✨ 已在愿望单</div>
                                      </div>
                                   </div>
                                    <div class="flex items-center">
                                        <!-- Wish button for unvisited -->
                                        <button v-if="wishlistSubTab === 'unvisited'" 
                                                @click="addToWorldWishlist(w)" 
                                                :disabled="hasInWorldWishlist(w.name)"
                                                class="p-2 transition-all rounded-lg"
                                                :class="hasInWorldWishlist(w.name) ? 'text-amber-500 cursor-default' : 'text-gray-500 hover:text-amber-500 hover:bg-amber-500/10'"
                                                :title="hasInWorldWishlist(w.name) ? '已在愿望单' : '加入愿望单'"
                                        >
                                           <svg class="w-5 h-5" :fill="hasInWorldWishlist(w.name) ? 'currentColor' : 'none'" stroke="currentColor" viewBox="0 0 24 24">
                                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.382-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"></path>
                                           </svg>
                                        </button>
                                        <!-- Delete button only for 'all' tab -->
                                        <button v-else-if="wishlistSubTab === 'all'" 
                                                @click="removeFromWorldWishlist(w)" 
                                                class="p-2 text-gray-500 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-all"
                                                title="移除"
                                        >
                                           <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                                        </button>
                                    </div>
                                </div>
                              </template>
                           </draggable>
                           <div v-if="displayWorldWishlist.length === 0" class="text-gray-600 text-center py-8 bg-gray-900/20 rounded-xl border border-dashed border-gray-800">暂无目的地</div>
                           <!-- Pagination Controls -->
                           <div v-if="displayWorldWishlist.length > wishlistPageSize" class="mt-4 flex items-center justify-between text-xs text-gray-400 px-2">
                             <button @click="wishlistPage.world[wishlistSubTab]--" :disabled="wishlistPage.world[wishlistSubTab] === 1" class="hover:text-white disabled:opacity-30 flex items-center gap-1">❮ Prev</button>
                             <span>{{ wishlistPage.world[wishlistSubTab] }} / {{ Math.ceil(displayWorldWishlist.length / wishlistPageSize) }}</span>
                             <button @click="wishlistPage.world[wishlistSubTab]++" :disabled="wishlistPage.world[wishlistSubTab] >= Math.ceil(displayWorldWishlist.length / wishlistPageSize)" class="hover:text-white disabled:opacity-30 flex items-center gap-1">Next ❯</button>
                           </div>
                        </div>

                        <!-- China Wishlist -->
                        <div class="bg-gray-800/80 backdrop-blur-md rounded-2xl p-6 border border-gray-700/50 shadow-xl">
                           <h3 class="text-xl font-bold text-white mb-6 flex items-center gap-3">
                               <span class="p-2 bg-red-500/20 rounded-lg text-red-400">🏯</span> 
                               华夏足迹
                           </h3>
                           <draggable 
                             v-model="paginatedChinaWishlist" 
                             class="space-y-3" 
                             handle=".drag-handle"
                             item-key="name"
                             :disabled="wishlistSubTab !== 'all'"
                           >
                              <template #item="{element: w}">
                                <div class="group flex justify-between items-center bg-gray-900/60 p-2.5 rounded-xl border transition-all duration-300"
                                     :class="visitedCities.has(w.name) ? 'border-green-500/30 bg-green-500/5' : 'border-gray-700 hover:border-blue-500/30'"
                                >
                                   <div class="flex items-center gap-4 cursor-pointer flex-1" @click="visitedCities.has(w.name) && selectPlaceByName(w.name)">
                                      <div v-if="wishlistSubTab === 'all'" class="drag-handle p-1 text-gray-600 hover:text-gray-400 cursor-grab active:cursor-grabbing">
                                         <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9h8M8 15h8"></path></svg>
                                      </div>
                                      <div class="w-10 h-10 bg-gray-800 rounded-lg flex items-center justify-center text-xl shadow-inner group-hover:bg-gray-700 transition-colors">📍</div>
                                      <div>
                                          <div class="text-gray-100 font-medium group-hover:text-white transition-colors flex items-center gap-2">
                                            {{ w.name }}
                                            <span v-if="w.province" class="text-[10px] bg-gray-700/50 text-gray-400 px-1 py-0.5 rounded">{{ w.province }}</span>
                                            <span v-if="popularCities.includes(w.name)" class="text-[9px] bg-amber-500/20 text-amber-500 px-1.5 py-0.5 rounded uppercase font-bold">Hot</span>
                                          </div>
                                          <div v-if="visitedCities.has(w.name) && wishlistSubTab === 'all'" class="text-[10px] text-green-400 font-bold uppercase tracking-wider mt-0.5">✅ 已打卡</div>
                                          <div v-else-if="!visitedCities.has(w.name) && wishlistSubTab === 'all'" class="text-[10px] text-gray-500 font-bold uppercase tracking-wider mt-0.5">⭐ 计划中</div>
                                          <div v-else-if="wishlistSubTab === 'unvisited' && hasInChinaWishlist(w.name)" class="text-[10px] text-amber-500 font-bold uppercase tracking-wider mt-0.5">✨ 已在愿望单</div>
                                      </div>
                                   </div>
                                   <div class="flex items-center">
                                       <!-- Wish button for unvisited -->
                                       <button v-if="wishlistSubTab === 'unvisited'" 
                                               @click="addToChinaWishlist(w)" 
                                               :disabled="hasInChinaWishlist(w.name)"
                                               class="p-2 transition-all rounded-lg"
                                               :class="hasInChinaWishlist(w.name) ? 'text-amber-500 cursor-default' : 'text-gray-500 hover:text-amber-500 hover:bg-amber-500/10'"
                                               :title="hasInChinaWishlist(w.name) ? '已在愿望单' : '加入愿望单'"
                                       >
                                          <svg class="w-5 h-5" :fill="hasInChinaWishlist(w.name) ? 'currentColor' : 'none'" stroke="currentColor" viewBox="0 0 24 24">
                                             <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.382-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"></path>
                                          </svg>
                                       </button>
                                       <!-- Delete button only for 'all' tab -->
                                       <button v-else-if="wishlistSubTab === 'all'" 
                                               @click="removeFromChinaWishlist(w)" 
                                               class="p-2 text-gray-500 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-all"
                                               title="移除"
                                       >
                                          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                                       </button>
                                   </div>
                                </div>
                              </template>
                           </draggable>
                           <div v-if="displayChinaWishlist.length === 0" class="text-gray-600 text-center py-8 bg-gray-900/20 rounded-xl border border-dashed border-gray-800">暂无收藏城市</div>
                           <!-- Pagination Controls -->
                           <div v-if="displayChinaWishlist.length > wishlistPageSize" class="mt-4 flex items-center justify-between text-xs text-gray-400 px-2">
                             <button @click="wishlistPage.china[wishlistSubTab]--" :disabled="wishlistPage.china[wishlistSubTab] === 1" class="hover:text-white disabled:opacity-30 flex items-center gap-1">❮ Prev</button>
                             <span>{{ wishlistPage.china[wishlistSubTab] }} / {{ Math.ceil(displayChinaWishlist.length / wishlistPageSize) }}</span>
                             <button @click="wishlistPage.china[wishlistSubTab]++" :disabled="wishlistPage.china[wishlistSubTab] >= Math.ceil(displayChinaWishlist.length / wishlistPageSize)" class="hover:text-white disabled:opacity-30 flex items-center gap-1">Next ❯</button>
                           </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Gallery Modal (Unified with Timeline) -->
    <div v-if="gallery.open" class="fixed inset-0 z-[5000] bg-black/95 flex flex-col" @keydown.esc="closeGallery" tabindex="0">
        <!-- Toolbar -->
        <div class="flex justify-between items-center p-4 text-white bg-black/50 backdrop-blur-sm z-30 absolute top-0 left-0 right-0">
           <span class="font-mono">{{ gallery.currentIndex + 1 }} / {{ gallery.currentItems.length }}</span>
           
           <div class="flex items-center gap-4">
               <button @click="revealInExplorer" class="text-white hover:text-blue-400 p-2 rounded hover:bg-white/10" title="在资源管理器中显示">
                   <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path></svg>
               </button>
               <button @click="trashCurrentItem" class="text-white hover:text-red-400 p-2 rounded hover:bg-white/10" title="移入回收站">
                   <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
               </button>
               <button @click="closeGallery" class="text-2xl font-bold p-2 hover:bg-white/20 rounded w-10 h-10 flex items-center justify-center">✕</button>
           </div>
        </div>
        
        <!-- Main Image/Video -->
        <div class="flex-1 flex items-center justify-center relative overflow-hidden">
            <button @click="prevImage" class="absolute left-4 z-20 text-white text-4xl p-4 hover:bg-white/10 rounded-full" v-if="gallery.currentIndex > 0">❮</button>
            
            <video v-if="isCurrentVideo" :src="gallery.currentImage" controls autoplay class="max-h-full max-w-full outline-none"></video>
            <img v-else :src="gallery.currentImage" class="max-h-full max-w-full object-contain select-none" />
            
            <button @click="nextImage" class="absolute right-4 z-20 text-white text-4xl p-4 hover:bg-white/10 rounded-full" v-if="gallery.currentIndex < gallery.currentItems.length - 1">❯</button>
        </div>

        <!-- Thumbnails Strip -->
        <div class="h-24 bg-black/80 flex items-center gap-2 overflow-x-auto p-2" ref="thumbStrip">
            <div 
              v-for="(item, idx) in gallery.currentItems" 
              :key="'thumb-'+idx"
              class="h-full aspect-square flex-shrink-0 cursor-pointer border-2"
              :class="idx === gallery.currentIndex ? 'border-red-500' : 'border-transparent opacity-60 hover:opacity-100'"
              @click="setGalleryIndex(idx)"
              :id="'thumb-' + idx"
            >
                <img :src="`${API_BASE}/files/thumbnail?path=${encodeURIComponent(item.file_path)}`" class="h-full w-full object-cover" />
            </div>
        </div>
    </div>
  </div>
</template>

<script setup>
import { API_BASE } from '../api/base'
import { ref, onMounted, nextTick, onUnmounted, computed, watch } from 'vue'
import axios from 'axios'
import draggable from 'vuedraggable'

import ChinaMap from '../components/ChinaMap.vue'

const tabs = [
  { id: 'world', label: '世界地图', icon: '🌍' },
  { id: 'china', label: '国内地图', icon: '🏯' },
  { id: 'list', label: '列表模式', icon: '📋' },
  { id: 'wishlist', label: '愿望清单', icon: '⭐' }
];

const places = ref([])
const placePhotosCache = ref({})
const selectedPlace = ref(null)
const photos = ref([])
const loading = ref(false)
const viewMode = ref('world')
const isFullscreen = ref(false)
const mapContainer = ref(null)
const isScanning = ref(false)

const chinaWishlist = ref([])
const worldWishlist = ref([])

const CHINA_TOURISM_CITIES = [
  { name: "北京", province: "北京" }, { name: "天津", province: "天津" }, { name: "上海", province: "上海" }, { name: "重庆", province: "重庆" },
  { name: "石家庄", province: "河北" }, { name: "秦皇岛", province: "河北" }, { name: "承德", province: "河北" }, { name: "廊坊", province: "河北" }, { name: "保定", province: "河北" }, { name: "邯郸", province: "河北" }, { name: "唐山", province: "河北" }, { name: "涿州", province: "河北" }, { name: "武安", province: "河北" }, { name: "遵化", province: "河北" },
  { name: "太原", province: "山西" }, { name: "大同", province: "山西" }, { name: "晋城", province: "山西" }, { name: "阳泉", province: "山西" }, { name: "长治", province: "山西" }, { name: "运城", province: "山西" }, { name: "侯马", province: "山西" }, { name: "孝义", province: "山西" },
  { name: "呼和浩特", province: "内蒙古" }, { name: "包头", province: "内蒙古" }, { name: "呼伦贝尔", province: "内蒙古" }, { name: "赤峰", province: "内蒙古" }, { name: "通辽", province: "内蒙古" }, { name: "鄂尔多斯", province: "内蒙古" }, { name: "满洲里", province: "内蒙古" }, { name: "扎兰屯", province: "内蒙古" }, { name: "阿尔山", province: "内蒙古" }, { name: "锡林浩特", province: "内蒙古" }, { name: "霍林郭勒", province: "内蒙古" },
  { name: "沈阳", province: "辽宁" }, { name: "大连", province: "辽宁" }, { name: "丹东", province: "辽宁" }, { name: "鞍山", province: "辽宁" }, { name: "抚顺", province: "辽宁" }, { name: "本溪", province: "辽宁" }, { name: "锦州", province: "辽宁" }, { name: "葫芦岛", province: "辽宁" }, { name: "辽阳", province: "辽宁" }, { name: "铁岭", province: "辽宁" }, { name: "盘锦", province: "辽宁" }, { name: "朝阳", province: "辽宁" }, { name: "营口", province: "辽宁" }, { name: "阜新", province: "辽宁" }, { name: "兴城", province: "辽宁" }, { name: "庄河", province: "辽宁" }, { name: "开原", province: "辽宁" }, { name: "凤城", province: "辽宁" },
  { name: "长春", province: "吉林" }, { name: "吉林", province: "吉林" }, { name: "蛟河", province: "吉林" }, { name: "集安", province: "吉林" }, { name: "延吉", province: "吉林" }, { name: "敦化", province: "吉林" }, { name: "桦甸", province: "吉林" },
  { name: "哈尔滨", province: "黑龙江" }, { name: "牡丹江", province: "黑龙江" }, { name: "伊春", province: "黑龙江" }, { name: "大庆", province: "黑龙江" }, { name: "齐齐哈尔", province: "黑龙江" }, { name: "黑河", province: "黑龙江" }, { name: "阿城", province: "黑龙江" }, { name: "绥芬河", province: "黑龙江" }, { name: "铁力", province: "黑龙江" }, { name: "虎林", province: "黑龙江" }, { name: "海林", province: "黑龙江" },
  { name: "南京", province: "江苏" }, { name: "无锡", province: "江苏" }, { name: "徐州", province: "江苏" }, { name: "常州", province: "江苏" }, { name: "苏州", province: "江苏" }, { name: "南通", province: "江苏" }, { name: "连云港", province: "江苏" }, { name: "淮安", province: "江苏" }, { name: "盐城", province: "江苏" }, { name: "扬州", province: "江苏" }, { name: "镇江", province: "江苏" }, { name: "泰州", province: "江苏" }, { name: "宿迁", province: "江苏" }, { name: "昆山", province: "江苏" }, { name: "江阴", province: "江苏" }, { name: "宜兴", province: "江苏" }, { name: "常熟", province: "江苏" }, { name: "张家港", province: "江苏" }, { name: "吴江", province: "江苏" }, { name: "启东", province: "江苏" }, { name: "海门", province: "江苏" }, { name: "如皋", province: "江苏" }, { name: "句容", province: "江苏" }, { name: "丹阳", province: "江苏" }, { name: "靖江", province: "江苏" }, { name: "兴化", province: "江苏" }, { name: "东台", province: "江苏" }, { name: "大丰", province: "江苏" },
  { name: "杭州", province: "浙江" }, { name: "宁波", province: "浙江" }, { name: "温州", province: "浙江" }, { name: "嘉兴", province: "浙江" }, { name: "湖州", province: "浙江" }, { name: "绍兴", province: "浙江" }, { name: "金华", province: "浙江" }, { name: "衢州", province: "浙江" }, { name: "舟山", province: "浙江" }, { name: "台州", province: "浙江" }, { name: "丽水", province: "浙江" }, { name: "义乌", province: "浙江" }, { name: "诸暨", province: "浙江" }, { name: "东阳", province: "浙江" }, { name: "永康", province: "浙江" }, { name: "临海", province: "浙江" }, { name: "温岭", province: "浙江" }, { name: "瑞安", province: "浙江" }, { name: "乐清", province: "浙江" }, { name: "建德", province: "浙江" }, { name: "临安", province: "浙江" },
  { name: "合肥", province: "安徽" }, { name: "芜湖", province: "安徽" }, { name: "黄山", province: "安徽" }, { name: "安庆", province: "安徽" }, { name: "马鞍山", province: "安徽" }, { name: "铜陵", province: "安徽" }, { name: "池州", province: "安徽" }, { name: "宣城", province: "安徽" }, { name: "亳州", province: "安徽" }, { name: "滁州", province: "安徽" }, { name: "宁国", province: "安徽" }, { name: "天长", province: "安徽" },
  { name: "福州", province: "福建" }, { name: "厦门", province: "福建" }, { name: "泉州", province: "福建" }, { name: "漳州", province: "福建" }, { name: "莆田", province: "福建" }, { name: "三明", province: "福建" }, { name: "南平", province: "福建" }, { name: "龙岩", province: "福建" }, { name: "宁德", province: "福建" }, { name: "武夷山", province: "福建" },
  { name: "南昌", province: "江西" }, { name: "九江", province: "江西" }, { name: "景德镇", province: "江西" }, { name: "萍乡", province: "江西" }, { name: "新余", province: "江西" }, { name: "鹰潭", province: "江西" }, { name: "赣州", province: "江西" }, { name: "宜春", province: "江西" }, { name: "上饶", province: "江西" }, { name: "吉安", province: "江西" }, { name: "井冈山", province: "江西" },
  { name: "济南", province: "山东" }, { name: "青岛", province: "山东" }, { name: "淄博", province: "山东" }, { name: "枣庄", province: "山东" }, { name: "东营", province: "山东" }, { name: "烟台", province: "山东" }, { name: "潍坊", province: "山东" }, { name: "济宁", province: "山东" }, { name: "泰安", province: "山东" }, { name: "威海", province: "山东" }, { name: "日照", province: "山东" }, { name: "莱芜", province: "山东" }, { name: "临沂", province: "山东" }, { name: "德州", province: "山东" }, { name: "聊城", province: "山东" }, { name: "滨州", province: "山东" }, { name: "菏泽", province: "山东" }, { name: "曲阜", province: "山东" }, { name: "蓬莱", province: "山东" }, { name: "青州", province: "山东" }, { name: "荣成", province: "山东" }, { name: "文登", province: "山东" }, { name: "寿光", province: "山东" }, { name: "胶州", province: "山东" }, { name: "乳山", province: "山东" }, { name: "滕州", province: "山东" },
  { name: "郑州", province: "河南" }, { name: "开封", province: "河南" }, { name: "洛阳", province: "河南" }, { name: "平顶山", province: "河南" }, { name: "安阳", province: "河南" }, { name: "鹤壁", province: "河南" }, { name: "新乡", province: "河南" }, { name: "焦作", province: "河南" }, { name: "濮阳", province: "河南" }, { name: "许昌", province: "河南" }, { name: "三门峡", province: "河南" }, { name: "南阳", province: "河南" }, { name: "信阳", province: "河南" }, { name: "周口", province: "河南" }, { name: "济源", province: "河南" },
  { name: "武汉", province: "湖北" }, { name: "黄石", province: "湖北" }, { name: "襄阳", province: "湖北" }, { name: "宜昌", province: "湖北" }, { name: "荆州", province: "湖北" }, { name: "十堰", province: "湖北" }, { name: "荆门", province: "湖北" }, { name: "鄂州", province: "湖北" }, { name: "孝感", province: "湖北" }, { name: "钟祥", province: "湖北" }, { name: "赤壁", province: "湖北" }, { name: "恩施", province: "湖北" }, { name: "利川", province: "湖北" },
  { name: "长沙", province: "湖南" }, { name: "株洲", province: "湖南" }, { name: "湘潭", province: "湖南" }, { name: "岳阳", province: "湖南" }, { name: "常德", province: "湖南" }, { name: "张家界", province: "湖南" }, { name: "益阳", province: "湖南" }, { name: "郴州", province: "湖南" }, { name: "永州", province: "湖南" }, { name: "娄底", province: "湖南" }, { name: "韶山", province: "湖南" }, { name: "资兴", province: "湖南" }, { name: "浏阳", province: "湖南" },
  { name: "广州", province: "广东" }, { name: "深圳", province: "广东" }, { name: "珠海", province: "广东" }, { name: "汕头", province: "广东" }, { name: "佛山", province: "广东" }, { name: "韶关", province: "广东" }, { name: "湛江", province: "广东" }, { name: "肇庆", province: "广东" }, { name: "江门", province: "广东" }, { name: "茂名", province: "广东" }, { name: "惠州", province: "广东" }, { name: "梅州", province: "广东" }, { name: "汕尾", province: "广东" }, { name: "河源", province: "广东" }, { name: "阳江", province: "广东" }, { name: "清远", province: "广东" }, { name: "东莞", province: "广东" }, { name: "中山", province: "广东" }, { name: "潮州", province: "广东" }, { name: "揭阳", province: "广东" }, { name: "云浮", province: "广东" }, { name: "南海", province: "广东" }, { name: "顺德", province: "广东" }, { name: "从化", province: "广东" },
  { name: "南宁", province: "广西" }, { name: "桂林", province: "广西" }, { name: "柳州", province: "广西" }, { name: "梧州", province: "广西" }, { name: "北海", province: "广西" }, { name: "钦州", province: "广西" }, { name: "玉林", province: "广西" }, { name: "百色", province: "广西" }, { name: "贺州", province: "广西" }, { name: "桂平", province: "广西" }, { name: "凭祥", province: "广西" }, { name: "宜州", province: "广西" },
  { name: "海口", province: "海南" }, { name: "三亚", province: "海南" }, { name: "琼海", province: "海南" }, { name: "儋州", province: "海南" }, { name: "琼山", province: "海南" },
  { name: "成都", province: "四川" }, { name: "乐山", province: "四川" }, { name: "绵阳", province: "四川" }, { name: "广安", province: "四川" }, { name: "自贡", province: "四川" }, { name: "宜宾", province: "四川" }, { name: "泸州", province: "四川" }, { name: "攀枝花", province: "四川" }, { name: "雅安", province: "四川" }, { name: "南充", province: "四川" }, { name: "德阳", province: "四川" }, { name: "广元", province: "四川" }, { name: "遂宁", province: "四川" }, { name: "峨眉山", province: "四川" }, { name: "都江堰", province: "四川" }, { name: "崇州", province: "四川" }, { name: "阆中", province: "四川" }, { name: "江油", province: "四川" }, { name: "西昌", province: "四川" }, { name: "华蓥", province: "四川" }, { name: "邛崃", province: "四川" },
  { name: "贵阳", province: "贵州" }, { name: "遵义", province: "贵州" }, { name: "安顺", province: "贵州" }, { name: "都匀", province: "贵州" }, { name: "凯里", province: "贵州" }, { name: "赤水", province: "贵州" }, { name: "兴义", province: "贵州" },
  { name: "昆明", province: "云南" }, { name: "丽江", province: "云南" }, { name: "保山", province: "云南" }, { name: "景洪", province: "云南" }, { name: "大理", province: "云南" }, { name: "瑞丽", province: "云南" }, { name: "潞西", province: "云南" },
  { name: "拉萨", province: "西藏" },
  { name: "西安", province: "陕西" }, { name: "咸阳", province: "陕西" }, { name: "宝鸡", province: "陕西" }, { name: "延安", province: "陕西" }, { name: "汉中", province: "陕西" }, { name: "韩城", province: "陕西" },
  { name: "兰州", province: "甘肃" }, { name: "天水", province: "甘肃" }, { name: "张掖", province: "甘肃" }, { name: "武威", province: "甘肃" }, { name: "酒泉", province: "甘肃" }, { name: "平凉", province: "甘肃" }, { name: "敦煌", province: "甘肃" }, { name: "嘉峪关", province: "甘肃" }, { name: "合作", province: "甘肃" },
  { name: "西宁", province: "青海" }, { name: "格尔木", province: "青海" },
  { name: "银川", province: "宁夏" },
  { name: "乌鲁木齐", province: "新疆" }, { name: "吐鲁番", province: "新疆" }, { name: "库尔勒", province: "新疆" }, { name: "喀什", province: "新疆" }, { name: "克拉玛依", province: "新疆" }, { name: "哈密", province: "新疆" }, { name: "阿克苏", province: "新疆" }, { name: "伊宁", province: "新疆" }, { name: "阿勒泰", province: "新疆" }, { name: "昌吉", province: "新疆" }, { name: "博乐", province: "新疆" }, { name: "阜康", province: "新疆" }, { name: "石河子", province: "新疆" }
];

const WORLD_TOURISM_CITIES = [
  // 欧洲 (40)
  { name: '伦敦', country: '英国' }, { name: '巴黎', country: '法国' }, { name: '罗马', country: '意大利' }, { name: '米兰', country: '意大利' }, { name: '威尼斯', country: '意大利' }, { name: '佛罗伦萨', country: '意大利' }, { name: '马德里', country: '西班牙' }, { name: '巴塞罗那', country: '西班牙' }, { name: '塞维利亚', country: '西班牙' }, { name: '柏林', country: '德国' },
  { name: '慕尼黑', country: '德国' }, { name: '法兰克福', country: '德国' }, { name: '阿姆斯特丹', country: '荷兰' }, { name: '维也纳', country: '奥地利' }, { name: '哈尔施塔特', country: '奥地利' }, { name: '布拉格', country: '捷克' }, { name: '布达佩斯', country: '匈牙利' }, { name: '苏黎世', country: '瑞士' }, { name: '日内瓦', country: '瑞士' }, { name: '里斯本', country: '葡萄牙' },
  { name: '波尔图', country: '葡萄牙' }, { name: '雅典', country: '希腊' }, { name: '圣托里尼', country: '希腊' }, { name: '伊斯坦布尔', country: '土耳其' }, { name: '安塔利亚', country: '土耳其' }, { name: '哥本哈根', country: '丹麦' }, { name: '斯德哥尔摩', country: '瑞典' }, { name: '奥斯陆', country: '挪威' }, { name: '赫尔辛基', country: '芬兰' }, { name: '雷克雅未克', country: '冰岛' },
  { name: '布鲁塞尔', country: '比利时' }, { name: '都柏林', country: '爱尔兰' }, { name: '华沙', country: '波兰' }, { name: '克拉科夫', country: '波兰' }, { name: '爱丁堡', country: '英国' }, { name: '尼斯', country: '法国' }, { name: '里昂', country: '法国' }, { name: '莫斯科', country: '俄罗斯' }, { name: '圣彼得堡', country: '俄罗斯' }, { name: '杜布罗夫尼克', country: '克罗地亚' },
  // 亚洲 (25)
  { name: '东京', country: '日本' }, { name: '大阪', country: '日本' }, { name: '京都', country: '日本' }, { name: '札幌', country: '日本' }, { name: '福冈', country: '日本' }, { name: '首尔', country: '韩国' }, { name: '釜山', country: '韩国' }, { name: '曼谷', country: '泰国' }, { name: '普吉岛', country: '泰国' }, { name: '清迈', country: '泰国' },
  { name: '芭提雅', country: '泰国' }, { name: '新加坡', country: '新加坡' }, { name: '吉隆坡', country: '马来西亚' }, { name: '槟城', country: '马来西亚' }, { name: '胡志明市', country: '越南' }, { name: '河内', country: '越南' }, { name: '岘港', country: '越南' }, { name: '巴厘岛', country: '印尼' }, { name: '雅加达', country: '印尼' }, { name: '马尼拉', country: '菲律宾' },
  { name: '长滩岛', country: '菲律宾' }, { name: '新德里', country: '印度' }, { name: '孟买', country: '印度' }, { name: '马累', country: '马尔代夫' }, { name: '科伦坡', country: '斯里兰卡' },
  // 美洲 (20)
  { name: '纽约', country: '美国' }, { name: '洛杉矶', country: '美国' }, { name: '拉斯维加斯', country: '美国' }, { name: '旧金山', country: '美国' }, { name: '奥兰多', country: '美国' }, { name: '迈阿密', country: '美国' }, { name: '芝加哥', country: '美国' }, { name: '华盛顿', country: '美国' }, { name: '多伦多', country: '加拿大' }, { name: '温哥华', country: '加拿大' },
  { name: '蒙特利尔', country: '加拿大' }, { name: '墨西哥城', country: '墨西哥' }, { name: '坎昆', country: '墨西哥' }, { name: '哈瓦那', country: '古巴' }, { name: '里约热内卢', country: '巴西' }, { name: '圣保罗', country: '巴西' }, { name: '布宜诺斯艾利斯', country: '阿根廷' }, { name: '利马', country: '秘鲁' }, { name: '圣地亚哥', country: '智利' }, { name: '波哥大', country: '哥伦比亚' },
  // 中东与非洲 (10)
  { name: '迪拜', country: '阿联酋' }, { name: '阿布扎比', country: '阿联酋' }, { name: '多哈', country: '卡塔尔' }, { name: '利雅得', country: '沙特' }, { name: '麦加', country: '沙特' }, { name: '开罗', country: '埃及' }, { name: '马拉喀什', country: '摩洛哥' }, { name: '卡萨布兰卡', country: '摩洛哥' }, { name: '开普敦', country: '南非' }, { name: '约翰内斯堡', country: '南非' },
  // 大洋洲 (5)
  { name: '悉尼', country: '澳洲' }, { name: '墨尔本', country: '澳洲' }, { name: '黄金海岸', country: '澳洲' }, { name: '奥克兰', country: '新西兰' }
];

const wishlistSubTab = ref('all')
const wishlistPage = ref({ 
    china: { all: 1, visited: 1, unvisited: 1 }, 
    world: { all: 1, visited: 1, unvisited: 1 } 
})
const wishlistPageSize = 20

// Popular Cities standard (sorted by photo count in places)
const popularCities = computed(() => {
    return [...places.value]
        .sort((a, b) => b.count - a.count)
        .slice(0, 50) 
        .map(p => (p.city || p.name.split(',')[0].trim()).replace('市', ''))
})

const visitedCities = computed(() => {
    const set = new Set()
    places.value.forEach(place => {
        if (place.city) set.add(place.city.replace('市', ''))
        const baseName = place.name.split(',')[0].trim().replace('市', '')
        if (baseName) set.add(baseName)
    })
    return set
})

const displayWorldWishlist = computed({
    get: () => {
        let list = []
        if (wishlistSubTab.value === 'visited') {
            const visited = places.value.filter(p => p.country && p.country !== 'China' && p.country !== '中国')
            const visitedNames = visited.map(p => (p.city || p.name.split(',')[0].trim()).replace('市', ''))
            list = WORLD_TOURISM_CITIES
                .filter(c => visitedNames.includes(c.name))
                .map(c => ({ name: c.name, country: c.country, flag: '📍' }))
        } else if (wishlistSubTab.value === 'unvisited') {
            list = WORLD_TOURISM_CITIES
                .filter(c => !visitedCities.value.has(c.name))
                .map(c => ({ name: c.name, country: c.country, flag: '🌍' }))
        } else {
            list = worldWishlist.value
        }
        return list
    },
    set: (val) => {
        if (wishlistSubTab.value === 'all') {
            worldWishlist.value = val
            saveWorldWishlist()
        }
    }
})

const paginatedWorldWishlist = computed(() => {
    const currentPage = wishlistPage.value.world[wishlistSubTab.value] || 1
    const start = (currentPage - 1) * wishlistPageSize
    return displayWorldWishlist.value.slice(start, start + wishlistPageSize)
})

const displayChinaWishlist = computed({
    get: () => {
        let list = []
        if (wishlistSubTab.value === 'visited') {
            const visitedNames = places.value
                .filter(p => !p.country || p.country === 'China' || p.country === '中国')
                .map(p => (p.city || p.name.split(',')[0].trim()).replace('市', ''))
            
            list = CHINA_TOURISM_CITIES
                .filter(c => visitedNames.includes(c.name))
                .map(c => ({ name: c.name, province: c.province }))
        } else if (wishlistSubTab.value === 'unvisited') {
            list = CHINA_TOURISM_CITIES
                .filter(c => !visitedCities.value.has(c.name))
                .map(c => ({ name: c.name, province: c.province }))
        } else {
            list = chinaWishlist.value.filter(c => CHINA_TOURISM_CITIES.some(tc => tc.name === c.name))
        }
        return list
    },
    set: (val) => {
        if (wishlistSubTab.value === 'all') {
            chinaWishlist.value = val
            saveChinaWishlist()
        }
    }
})

const paginatedChinaWishlist = computed(() => {
    const currentPage = wishlistPage.value.china[wishlistSubTab.value] || 1
    const start = (currentPage - 1) * wishlistPageSize
    return displayChinaWishlist.value.slice(start, start + wishlistPageSize)
})

const searchQuery = ref('')
const currentPage = ref(1)
const listPageSize = 25
const gallery = ref({
    open: false,
    currentItems: [],
    currentIndex: 0,
    currentImage: ''
})

const getFileUrl = (path) => `${API_BASE}/files/content?path=${encodeURIComponent(path)}`

const isCurrentVideo = computed(() => {
    const item = gallery.value.currentItems[gallery.value.currentIndex]
    return item && item.tag === 'video'
})

const openGallery = (sourceItems, index) => {
    gallery.value.currentItems = sourceItems
    gallery.value.currentIndex = index
    
    const item = sourceItems[index]
    if(item) gallery.value.currentImage = getFileUrl(item.file_path)
    
    gallery.value.open = true
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', handleKey)
    
    scrollToThumb('auto')
}

const closeGallery = () => {
    gallery.value.open = false
    document.body.style.overflow = ''
    window.removeEventListener('keydown', handleKey)
}

const updateImage = () => {
    const item = gallery.value.currentItems[gallery.value.currentIndex]
    if(item) {
        gallery.value.currentImage = getFileUrl(item.file_path)
        scrollToThumb()
    }
}

const prevImage = () => {
    if (gallery.value.currentIndex > 0) {
        gallery.value.currentIndex--
        updateImage()
    }
}

const nextImage = () => {
    if (gallery.value.currentIndex < gallery.value.currentItems.length - 1) {
        gallery.value.currentIndex++
        updateImage()
    }
}

const setGalleryIndex = (idx) => {
    gallery.value.currentIndex = idx
    updateImage()
}

const handleKey = (e) => {
    if (e.key === 'ArrowLeft') prevImage()
    if (e.key === 'ArrowRight') nextImage()
    if (e.key === 'Escape') closeGallery()
    if (e.key === 'Delete' || e.key === 'Backspace') trashCurrentItem()
}

const revealInExplorer = async () => {
    const item = gallery.value.currentItems[gallery.value.currentIndex]
    if (!item) return
    
    try {
        await axios.post(`${API_BASE}/system/explorer`, {
            path: item.file_path
        })
    } catch (e) {
        console.error("Failed to reveal in explorer", e)
    }
}

const trashCurrentItem = async () => {
    const item = gallery.value.currentItems[gallery.value.currentIndex]
    if (!item) return
    
    if (!confirm("确定要移入回收站吗？")) return

    try {
        await axios.post(`${API_BASE}/files/trash`, {
            file_paths: [item.file_path]
        })
        
        photos.value = photos.value.filter(p => p.file_path !== item.file_path)
        gallery.value.currentItems.splice(gallery.value.currentIndex, 1)
        
        if (gallery.value.currentItems.length === 0) {
            closeGallery()
        } else {
            if (gallery.value.currentIndex >= gallery.value.currentItems.length) {
                gallery.value.currentIndex = gallery.value.currentItems.length - 1
            }
            updateImage()
        }
    } catch (e) {
        alert("删除失败: " + e)
    }
}

const thumbStrip = ref(null)
const scrollToThumb = (behavior = 'smooth') => {
    nextTick(() => {
        const el = document.getElementById('thumb-' + gallery.value.currentIndex)
        if (el && thumbStrip.value) {
            el.scrollIntoView({ behavior: behavior, block: 'nearest', inline: 'center' })
        }
    })
}

const filteredPlaces = computed(() => {
    if (!searchQuery.value) return places.value
    const q = searchQuery.value.toLowerCase()
    return places.value.filter(p => p.name.toLowerCase().includes(q) || (p.city && p.city.toLowerCase().includes(q)))
})

const totalPages = computed(() => Math.ceil(filteredPlaces.value.length / listPageSize))
const paginatedPlaces = computed(() => filteredPlaces.value.slice((currentPage.value-1)*listPageSize, currentPage.value*listPageSize))

const fetchPlaces = async () => {
    try {
        const res = await fetch(`${API_BASE}/files/organize/places`)
        places.value = await res.json()
    } catch (e) { console.error(e) }
}

const selectPlace = async (place) => {
    selectedPlace.value = place
    if (placePhotosCache.value[place.name]) {
        photos.value = placePhotosCache.value[place.name]
        return
    }
    loading.value = true
    try {
        const res = await fetch(`${API_BASE}/files/organize/places/${encodeURIComponent(place.name)}`)
        photos.value = await res.json()
        placePhotosCache.value[place.name] = photos.value
    } catch (e) { console.error(e) } finally { loading.value = false }
}

const selectPlaceByName = (cityName) => {
    const place = places.value.find(p => p.name.includes(cityName) || (p.city && p.city.includes(cityName)))
    if (place) selectPlace(place)
}

let mapInstance = null
let clusterGroup = null

const initMap = async () => {
    if (mapInstance || !mapContainer.value || !window.L) return;
    loading.value = true;
    try {
        await nextTick();
        const L = window.L;
        mapInstance = L.map(mapContainer.value, { zoomControl: false }).setView([20, 10], 2.5);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(mapInstance);
        
        clusterGroup = L.markerClusterGroup({
            showCoverageOnHover: false,
            maxClusterRadius: 50,
            spiderfyOnMaxZoom: true,
            disableClusteringAtZoom: 16
        });
        mapInstance.addLayer(clusterGroup);
        
        if (places.value.length === 0) await fetchPlaces();
        const mapData = places.value.filter(p => p.latitude && p.longitude);
        
        const markers = mapData.map(p => {
            const icon = L.divIcon({
              className: 'custom-map-icon',
              html: `<div class="w-8 h-8 rounded-full border-2 border-white shadow bg-blue-500 overflow-hidden"><img src="${API_BASE}/files/thumbnail?path=${encodeURIComponent(p.cover.file_path)}" class="w-full h-full object-cover" loading="lazy"></div>`,
              iconSize: [32, 32]
            });
            return L.marker([p.latitude, p.longitude], { icon }).on('click', () => selectPlace(p));
        });
        
        if (markers.length > 0) {
            clusterGroup.addLayers(markers);
        }
    } catch (e) {
        console.error("Map init failed", e);
    } finally {
        loading.value = false;
    }
}

const switchView = (mode) => {
    viewMode.value = mode;
    if (mode === 'world') {
        nextTick(() => {
            if (mapInstance) {
                mapInstance.invalidateSize();
            } else {
                initMap();
            }
        });
    }
}

watch(selectedPlace, (newVal) => {
    if (!newVal && viewMode.value === 'world') {
        nextTick(() => {
            if (mapInstance) {
                mapInstance.invalidateSize();
            } else {
                initMap();
            }
        });
    }
});

const toggleFullscreen = () => { isFullscreen.value = !isFullscreen.value; }

const rescanCities = async () => {
    isScanning.value = true;
    try {
        await fetch(`${API_BASE}/files/organize/places/rescan_cities`, { method: 'POST' });
        await fetchPlaces();
    } catch (e) { console.error(e) } finally { isScanning.value = false }
}

const loadWishlists = async () => {
    try {
        const res1 = await fetch(`${API_BASE}/config/wishlist`);
        chinaWishlist.value = await res1.json();
        const res2 = await fetch(`${API_BASE}/config/world_wishlist`);
        worldWishlist.value = await res2.json();
    } catch (e) {}
}

const saveChinaWishlist = async () => {
    await fetch(`${API_BASE}/config/wishlist`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({wishlist: chinaWishlist.value}) });
}

const saveWorldWishlist = async () => {
    await fetch(`${API_BASE}/config/world_wishlist`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({wishlist: worldWishlist.value}) });
}

const addToChinaWishlist = async (city) => {
    if (chinaWishlist.value.some(w => w.name === city.name)) return;
    chinaWishlist.value.push({ name: city.name, province: city.province });
    await saveChinaWishlist();
}

const addToWorldWishlist = async (city) => {
    if (worldWishlist.value.some(w => w.name === city.name)) return;
    worldWishlist.value.push({ name: city.name, country: city.country, flag: city.flag || '🌍' });
    await saveWorldWishlist();
}

const hasInChinaWishlist = (name) => chinaWishlist.value.some(w => w.name === name);
const hasInWorldWishlist = (name) => worldWishlist.value.some(w => w.name === name);

const removeFromChinaWishlist = async (city) => {
    chinaWishlist.value = chinaWishlist.value.filter(w => w.name !== city.name);
    await saveChinaWishlist();
}

const removeFromWorldWishlist = async (city) => {
    worldWishlist.value = worldWishlist.value.filter(w => w.name !== city.name);
    await saveWorldWishlist();
}

const handleChinaMapPlaceClick = (name) => {
  const p = places.value.find(x => x.name.includes(name) || (x.city && x.city.includes(name)));
  if (p) selectPlace(p);
}

const hasMapData = computed(() => places.value.some(p => p.latitude && p.longitude))

onMounted(() => {
    fetchPlaces();
    loadWishlists();
    nextTick(() => initMap());
})

onUnmounted(() => { if (mapInstance) mapInstance.remove() })
</script>

<style scoped>
.animate-fade-in { animation: fadeIn 0.3s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: scale(0.98); } to { opacity: 1; transform: scale(1); } }
.pulse-glow { animation: pulse 2s infinite; background: #1a1a1a; }
@keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
.custom-scrollbar::-webkit-scrollbar { width: 4px; height: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #333; border-radius: 4px; }
div::-webkit-scrollbar {
  height: 8px;
  background-color: #000;
}
div::-webkit-scrollbar-thumb {
  background-color: #333;
  border-radius: 4px;
}
</style>
<style>
.custom-map-icon { background: none !important; border: none !important; }
</style>
