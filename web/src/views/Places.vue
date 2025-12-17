<template>
  <div class="h-full flex flex-col bg-gray-50">
    <!-- Header -->
    <div class="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between shadow-sm z-10">
      <div class="flex items-center gap-4">
        <button v-if="selectedPlace" @click="selectedPlace = null" class="text-gray-500 hover:text-gray-900">
           ← 返回
        </button>
        <span class="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-green-500 to-teal-600">
          {{ selectedPlace ? selectedPlace.name : '地点 (Places)' }}
        </span>
         <span v-if="selectedPlace" class="text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
            {{ photos.length }} photos
        </span>
      </div>
    </div>

    <!-- Content -->
    <!-- Content -->
    <div class="flex-1 overflow-hidden relative">
        <!-- Controls (Map/List Toggle) - Only show if NO selected place -->
        <div v-if="!selectedPlace" class="absolute top-4 right-6 z-[1000] flex gap-2">
            <button @click="toggleView" class="bg-white shadow-md px-3 py-1.5 rounded-full text-sm font-medium hover:bg-gray-50 flex items-center gap-1 transition-all">
                <span v-if="!showMap">🗺️ 地图模式</span>
                <span v-else>📋 列表模式</span>
            </button>
        </div>

        <!-- Detail View (Photos) - Top Level Priority -->
        <div v-if="selectedPlace" class="h-full overflow-y-auto p-6 scroll-smooth">
             <div class="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
                <!-- Photos -->
                 <div 
                    v-for="(photo, idx) in photos" 
                    :key="photo.file_path"
                    class="relative group aspect-square bg-gray-100 rounded-lg overflow-hidden cursor-pointer"
                    @click="openLightbox(idx)"
                >
                    <img 
                        loading="lazy"
                        :src="`http://localhost:8000/files/thumbnail?path=${encodeURIComponent(photo.file_path)}`" 
                        class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" 
                    />
                </div>
            </div>
        </div>

        <!-- Main View (Map or List) -->
        <div v-else class="w-full h-full">
            <!-- Map View -->
            <div v-if="showMap" class="w-full h-full relative">
                <div ref="mapContainer" class="w-full h-full bg-gray-100"></div>
                <!-- Map Overlay: Empty State -->
                 <div v-if="!loading && !hasMapData" class="absolute inset-0 flex items-center justify-center pointer-events-none">
                     <div class="bg-white/90 p-6 rounded-xl shadow-lg text-center backdrop-blur pointer-events-auto">
                        <div class="text-4xl mb-2">🌍</div>
                        <p class="text-gray-600">地图暂无数据 (No GPS data)</p>
                        <p class="text-xs text-gray-400 mt-1">请尝试重建索引 (Re-index required)</p>
                     </div>
                 </div>
            </div>

            <!-- List View -->
            <div v-else class="h-full overflow-y-auto p-6 scroll-smooth">
                 <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
                    <div 
                        v-for="place in places" 
                        :key="place.name"
                        class="group bg-white rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300 cursor-pointer overflow-hidden transform hover:-translate-y-1"
                        @click="selectPlace(place)"
                    >
                        <!-- Cover -->
                        <div class="relative aspect-square bg-gray-100 overflow-hidden">
                            <img 
                                loading="lazy"
                                :src="`http://localhost:8000/files/thumbnail?path=${encodeURIComponent(place.cover.file_path)}`" 
                                class="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" 
                            />
                            <div class="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-black/60 to-transparent"></div>
                            <div class="absolute bottom-3 left-3 text-white">
                                 <div class="font-bold text-lg leading-tight">{{ place.name }}</div>
                                 <div class="text-xs opacity-80">{{ place.count }} photos</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                 <!-- Empty State -->
                <div v-if="!loading && places.length === 0" class="flex flex-col items-center justify-center h-full text-gray-400 py-20">
                     <div class="text-5xl mb-4">🌍</div>
                     <p>没有找到地点数据 (No places found)</p>
                     <p class="text-xs mt-2">请尝试重新建立索引 (Try re-indexing)</p>
                </div>
            </div>
        </div>

        <!-- Loading -->
        <div v-if="loading" class="fixed inset-0 flex items-center justify-center bg-white/50 z-50">
            <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-green-500"></div>
        </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, onUnmounted, computed, watch } from 'vue'

const places = ref([])
const selectedPlace = ref(null)
const photos = ref([])
const loading = ref(false)
const showMap = ref(true) // Default to map view per user request
const mapContainer = ref(null)
let mapInstance = null

const hasMapData = computed(() => {
    return places.value.some(p => p.latitude && p.longitude)
})

const fetchPlaces = async () => {
    loading.value = true
    try {
        const res = await fetch('http://localhost:8000/files/organize/places')
        places.value = await res.json()
    } catch (e) {
        console.error(e)
    } finally {
        loading.value = false
    }
}

const selectPlace = async (place) => {
    selectedPlace.value = place
    loading.value = true
    try {
        const res = await fetch(`http://localhost:8000/files/organize/places/${encodeURIComponent(place.name)}`)
        photos.value = await res.json()
    } catch (e) {
        console.error(e)
    } finally {
        loading.value = false
    }
}
// Watch navigation to handle map lifecycle
watch(selectedPlace, async (newVal) => {
    if (newVal) {
        // Leaving Map view (if active) -> Cleanup
        if (mapInstance) {
            mapInstance.remove()
            mapInstance = null
        }
    } else {
        // Returning to main view
        if (showMap.value) {
            await nextTick()
            initMap()
        }
    }
})

// Map Logic
const initMap = async () => {
    if (mapInstance) return
    
    // Wait for DOM
    await nextTick()
    if (!mapContainer.value) return

    loading.value = true
    try {
        if (places.value.length === 0) {
            await fetchPlaces()
        }

        // Use grouped places data instead of raw points
        const mapData = places.value.filter(p => p.latitude && p.longitude)

        if (mapData.length === 0) {
             loading.value = false
             return
        }

        const L = window.L
        // Default center (China) or first photo
        const center = [mapData[0].latitude, mapData[0].longitude]
        
        mapInstance = L.map(mapContainer.value).setView(center, 5)

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19
        }).addTo(mapInstance)

        // Add Custom Markers (Cards)
        const markers = L.layerGroup().addTo(mapInstance)
        
        mapData.forEach(p => {
             // Custom HTML Icon
             const iconHtml = `
                <div class="relative group cursor-pointer transform hover:scale-110 transition-transform duration-300">
                    <div class="w-16 h-16 md:w-20 md:h-20 rounded-xl overflow-hidden shadow-lg border-2 border-white bg-white">
                        <img src="http://localhost:8000/files/thumbnail?path=${encodeURIComponent(p.cover.file_path)}" class="w-full h-full object-cover"/>
                    </div>
                    <div class="absolute -bottom-2 left-1/2 transform -translate-x-1/2 bg-white/90 backdrop-blur px-2 py-0.5 rounded-full text-[10px] font-bold shadow-sm whitespace-nowrap">
                        ${p.name}
                    </div>
                    <div class="absolute -top-2 -right-2 bg-green-500 text-white text-[10px] w-5 h-5 flex items-center justify-center rounded-full border border-white shadow-sm">
                        ${p.count}
                    </div>
                </div>
             `
             
             const customIcon = L.divIcon({
                 className: 'custom-map-marker', // Clean, no default styles
                 html: iconHtml,
                 iconSize: [80, 80],
                 iconAnchor: [40, 40]
             })

             const marker = L.marker([p.latitude, p.longitude], { icon: customIcon })
                .addTo(markers)
                .on('click', () => {
                    selectPlace(p)
                })
        })

        // Fit bounds
        if (mapData.length > 0) {
            const group = new L.featureGroup(mapData.map(p => L.marker([p.latitude, p.longitude])))
            mapInstance.fitBounds(group.getBounds().pad(0.1))
        }

    } catch (e) {
        console.error("Map init error:", e)
    } finally {
        loading.value = false
    }
}

const toggleView = () => {
    showMap.value = !showMap.value
    if (showMap.value) {
        initMap()
    } else {
        if (mapInstance) {
            mapInstance.remove()
            mapInstance = null
        }
        fetchPlaces()
    }
}

onMounted(() => {
    // Check if we should show map instantly
    if (showMap.value) {
        initMap()
    } else {
        fetchPlaces()
    }
})

onUnmounted(() => {
    if (mapInstance) {
        mapInstance.remove()
    }
})
</script>

<style>
/* Global or deep selector to override Leaflet default styles */
.custom-map-marker {
  background: transparent !important;
  border: none !important;
}
</style>
