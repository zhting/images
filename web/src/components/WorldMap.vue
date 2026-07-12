<template>
  <div class="flex h-full">
    <!-- ECharts Map Container -->
    <div class="flex-1 relative">
      <!-- Map -->
      <div ref="chartContainer" class="w-full h-full"></div>
    </div>

    <!-- Wishlist Sidebar -->
    <transition name="slide">
      <div
        v-if="showWishlist"
        class="w-80 bg-gray-900 border-l border-gray-800 p-4 overflow-y-auto"
      >
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-white font-bold">🌍 全球愿望清单</h3>
          <button @click="showWishlist = false" class="text-gray-400 hover:text-white">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Wishlist Items -->
        <div v-if="wishlist.length > 0" class="space-y-2 mb-6">
          <div
            v-for="(city, index) in wishlist"
            :key="'w-' + city.name"
            class="bg-yellow-900/30 border border-yellow-600/50 rounded-lg p-3 cursor-move text-white text-sm"
            draggable="true"
            @dragstart="dragStartWishlist(index)"
            @dragover.prevent
            @drop="dropWishlist(index)"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-yellow-500 text-xs">{{ index + 1 }}</span>
                <span>{{ city.flag }} {{ city.name }}</span>
                <span class="text-gray-500 text-xs">({{ city.country }})</span>
              </div>
              <button
                @click="removeFromWishlist(city)"
                class="text-gray-400 hover:text-red-400"
                title="移除"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- Unvisited Popular Cities -->
        <div class="mt-4">
          <h4 class="text-gray-400 font-bold text-sm mb-3">热门城市</h4>
          <div class="space-y-2">
            <div
              v-for="city in unvisitedCities"
              :key="city.name"
              class="bg-gray-800 rounded-lg p-3 text-white text-sm flex items-center justify-between"
            >
              <div class="flex items-center gap-2">
                <span>{{ city.flag }} {{ city.name }}</span>
                <span class="text-gray-500 text-xs">({{ city.country }})</span>
              </div>
              <button
                @click="addToWishlist(city)"
                class="text-yellow-600 hover:text-yellow-400"
                title="添加到愿望清单"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-if="unvisitedCities.length === 0 && wishlist.length === 0" class="text-gray-500 text-sm text-center py-8">
          暂无数据
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick, onUnmounted } from 'vue'
import * as echarts from 'echarts/core'
import { ScatterChart, MapChart } from 'echarts/charts'
import { TooltipComponent, VisualMapComponent, GeoComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([ScatterChart, MapChart, TooltipComponent,
             VisualMapComponent, GeoComponent, CanvasRenderer])

const props = defineProps({
  fullscreen: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:fullscreen'])

// Refs
const chartContainer = ref(null)
const showWishlist = ref(false)
const wishlist = ref([])
const dragIndex = ref(-1)
let chartInstance = null

// Global popular tourist cities (excluding China)
const popularCities = [
  // Asia
  { name: '东京', country: '日本', flag: '🇯🇵', lng: 139.69, lat: 35.69 },
  { name: '大阪', country: '日本', flag: '🇯🇵', lng: 135.50, lat: 34.69 },
  { name: '京都', country: '日本', flag: '🇯🇵', lng: 135.77, lat: 35.01 },
  { name: '首尔', country: '韩国', flag: '🇰🇷', lng: 126.98, lat: 37.57 },
  { name: '济州岛', country: '韩国', flag: '🇰🇷', lng: 126.53, lat: 33.50 },
  { name: '曼谷', country: '泰国', flag: '🇹🇭', lng: 100.50, lat: 13.75 },
  { name: '清迈', country: '泰国', flag: '🇹🇭', lng: 98.98, lat: 18.79 },
  { name: '普吉岛', country: '泰国', flag: '🇹🇭', lng: 98.39, lat: 7.88 },
  { name: '新加坡', country: '新加坡', flag: '🇸🇬', lng: 103.82, lat: 1.35 },
  { name: '吉隆坡', country: '马来西亚', flag: '🇲🇾', lng: 101.69, lat: 3.14 },
  { name: '巴厘岛', country: '印度尼西亚', flag: '🇮🇩', lng: 115.09, lat: -8.34 },
  { name: '河内', country: '越南', flag: '🇻🇳', lng: 105.85, lat: 21.03 },
  { name: '胡志明市', country: '越南', flag: '🇻🇳', lng: 106.63, lat: 10.82 },
  { name: '金边', country: '柬埔寨', flag: '🇰🇭', lng: 104.92, lat: 11.56 },
  { name: '暹粒', country: '柬埔寨', flag: '🇰🇭', lng: 103.86, lat: 13.36 },
  { name: '马尼拉', country: '菲律宾', flag: '🇵🇭', lng: 120.98, lat: 14.60 },
  { name: '新德里', country: '印度', flag: '🇮🇳', lng: 77.21, lat: 28.61 },
  { name: '迪拜', country: '阿联酋', flag: '🇦🇪', lng: 55.27, lat: 25.20 },
  { name: '伊斯坦布尔', country: '土耳其', flag: '🇹🇷', lng: 28.98, lat: 41.01 },
  { name: '马尔代夫', country: '马尔代夫', flag: '🇲🇻', lng: 73.51, lat: 4.18 },

  // Europe
  { name: '巴黎', country: '法国', flag: '🇫🇷', lng: 2.35, lat: 48.86 },
  { name: '尼斯', country: '法国', flag: '🇫🇷', lng: 7.26, lat: 43.71 },
  { name: '伦敦', country: '英国', flag: '🇬🇧', lng: -0.12, lat: 51.51 },
  { name: '罗马', country: '意大利', flag: '🇮🇹', lng: 12.50, lat: 41.90 },
  { name: '威尼斯', country: '意大利', flag: '🇮🇹', lng: 12.34, lat: 45.44 },
  { name: '佛罗伦萨', country: '意大利', flag: '🇮🇹', lng: 11.25, lat: 43.77 },
  { name: '米兰', country: '意大利', flag: '🇮🇹', lng: 9.19, lat: 45.46 },
  { name: '巴塞罗那', country: '西班牙', flag: '🇪🇸', lng: 2.17, lat: 41.39 },
  { name: '马德里', country: '西班牙', flag: '🇪🇸', lng: -3.70, lat: 40.42 },
  { name: '阿姆斯特丹', country: '荷兰', flag: '🇳🇱', lng: 4.90, lat: 52.37 },
  { name: '柏林', country: '德国', flag: '🇩🇪', lng: 13.40, lat: 52.52 },
  { name: '慕尼黑', country: '德国', flag: '🇩🇪', lng: 11.58, lat: 48.14 },
  { name: '维也纳', country: '奥地利', flag: '🇦🇹', lng: 16.37, lat: 48.21 },
  { name: '布拉格', country: '捷克', flag: '🇨🇿', lng: 14.42, lat: 50.08 },
  { name: '布达佩斯', country: '匈牙利', flag: '🇭🇺', lng: 19.04, lat: 47.50 },
  { name: '雅典', country: '希腊', flag: '🇬🇷', lng: 23.73, lat: 37.98 },
  { name: '圣托里尼', country: '希腊', flag: '🇬🇷', lng: 25.43, lat: 36.39 },
  { name: '苏黎世', country: '瑞士', flag: '🇨🇭', lng: 8.54, lat: 47.38 },
  { name: '卢塞恩', country: '瑞士', flag: '🇨🇭', lng: 8.31, lat: 47.05 },
  { name: '莫斯科', country: '俄罗斯', flag: '🇷🇺', lng: 37.62, lat: 55.76 },
  { name: '赫尔辛基', country: '芬兰', flag: '🇫🇮', lng: 24.94, lat: 60.17 },
  { name: '斯德哥尔摩', country: '瑞典', flag: '🇸🇪', lng: 18.07, lat: 59.33 },
  { name: '哥本哈根', country: '丹麦', flag: '🇩🇰', lng: 12.57, lat: 55.68 },
  { name: '里斯本', country: '葡萄牙', flag: '🇵🇹', lng: -9.14, lat: 38.74 },
  { name: '克罗地亚杜布罗夫尼克', country: '克罗地亚', flag: '🇭🇷', lng: 18.09, lat: 42.65 },

  // Americas
  { name: '纽约', country: '美国', flag: '🇺🇸', lng: -74.01, lat: 40.71 },
  { name: '洛杉矶', country: '美国', flag: '🇺🇸', lng: -118.24, lat: 34.05 },
  { name: '旧金山', country: '美国', flag: '🇺🇸', lng: -122.42, lat: 37.78 },
  { name: '拉斯维加斯', country: '美国', flag: '🇺🇸', lng: -115.14, lat: 36.17 },
  { name: '夏威夷', country: '美国', flag: '🇺🇸', lng: -155.50, lat: 19.90 },
  { name: '温哥华', country: '加拿大', flag: '🇨🇦', lng: -123.12, lat: 49.28 },
  { name: '多伦多', country: '加拿大', flag: '🇨🇦', lng: -79.38, lat: 43.65 },
  { name: '坎昆', country: '墨西哥', flag: '🇲🇽', lng: -86.85, lat: 21.16 },
  { name: '里约热内卢', country: '巴西', flag: '🇧🇷', lng: -43.17, lat: -22.91 },
  { name: '布宜诺斯艾利斯', country: '阿根廷', flag: '🇦🇷', lng: -58.38, lat: -34.60 },
  { name: '利马', country: '秘鲁', flag: '🇵🇪', lng: -77.04, lat: -12.05 },

  // Oceania
  { name: '悉尼', country: '澳大利亚', flag: '🇦🇺', lng: 151.21, lat: -33.87 },
  { name: '墨尔本', country: '澳大利亚', flag: '🇦🇺', lng: 144.96, lat: -37.81 },
  { name: '奥克兰', country: '新西兰', flag: '🇳🇿', lng: 174.76, lat: -36.85 },
  { name: '皇后镇', country: '新西兰', flag: '🇳🇿', lng: 168.66, lat: -45.03 },

  // Africa
  { name: '开罗', country: '埃及', flag: '🇪🇬', lng: 31.24, lat: 30.04 },
  { name: '开普敦', country: '南非', flag: '🇿🇦', lng: 18.42, lat: -33.93 },
  { name: '马拉喀什', country: '摩洛哥', flag: '🇲🇦', lng: -8.00, lat: 31.63 },
  { name: '内罗毕', country: '肯尼亚', flag: '🇰🇪', lng: 36.82, lat: -1.29 },
]

// Computed
const unvisitedCities = computed(() => {
  return popularCities.filter(city =>
    !wishlist.value.some(w => w.name === city.name)
  ).slice(0, 20)
})

// Functions
function initChart() {
  if (!chartContainer.value) return

  chartInstance = echarts.init(chartContainer.value)

  // Prepare city data
  const cityData = popularCities.map(city => {
    let itemStyle = { color: '#6b7280' } // gray - default
    let symbolSize = 8

    if (wishlist.value.some(w => w.name === city.name)) {
      itemStyle = { color: '#eab308' } // yellow - wishlist
      symbolSize = 12
    }

    return {
      name: city.name,
      value: [city.lng, city.lat],
      itemStyle,
      symbolSize,
      label: {
        show: symbolSize > 8,
        formatter: city.name,
        position: 'right',
        color: '#eab308',
        fontSize: 10
      }
    }
  })

  const option = {
    backgroundColor: '#1a1a2e',
    tooltip: {
      trigger: 'item',
      formatter: function(params) {
        if (params.seriesType === 'scatter') {
          const city = popularCities.find(c => c.name === params.name)
          const inWishlist = wishlist.value.some(w => w.name === params.name)
          return `${city?.flag || ''} ${params.name}<br/>国家: ${city?.country}<br/>状态: ${inWishlist ? '⭐ 愿望清单' : '未添加'}`
        }
        return params.name
      }
    },
    geo: {
      map: 'world',
      roam: true,
      zoom: 1.5,
      center: [20, 30],
      itemStyle: {
        areaColor: '#2a2a4a',
        borderColor: '#404070'
      },
      emphasis: {
        itemStyle: {
          areaColor: '#3a3a5a'
        },
        label: {
          show: false
        }
      },
      label: {
        show: false
      },
      // Highlight China in a special color
      regions: [
        {
          name: 'China',
          itemStyle: {
            areaColor: '#3d5a3d'
          }
        }
      ]
    },
    series: [
      {
        name: '城市',
        type: 'scatter',
        coordinateSystem: 'geo',
        data: cityData,
        itemStyle: {
          shadowBlur: 10,
          shadowColor: 'rgba(0,0,0,0.5)'
        },
        emphasis: {
          scale: 1.8
        }
      }
    ]
  }

  chartInstance.setOption(option)

  // Click handler - toggle wishlist on click
  chartInstance.on('click', function(params) {
    if (params.seriesType === 'scatter') {
      const city = popularCities.find(c => c.name === params.name)
      if (city) {
        if (wishlist.value.some(w => w.name === city.name)) {
          removeFromWishlist(city)
        } else {
          addToWishlist(city)
        }
      }
    }
  })

  // Resize handler
  const resizeHandler = () => chartInstance?.resize()
  window.addEventListener('resize', resizeHandler)
}

function toggleWishlist() {
  showWishlist.value = !showWishlist.value
}

// Wishlist management
function addToWishlist(city) {
  if (!wishlist.value.some(w => w.name === city.name)) {
    wishlist.value.push({ name: city.name, country: city.country, flag: city.flag })
    saveWishlist()
    updateChart()
  }
}

function removeFromWishlist(city) {
  wishlist.value = wishlist.value.filter(w => w.name !== city.name)
  saveWishlist()
  updateChart()
}

function dragStartWishlist(index) {
  dragIndex.value = index
}

function dropWishlist(index) {
  const list = [...wishlist.value]
  const [moved] = list.splice(dragIndex.value, 1)
  list.splice(index, 0, moved)
  wishlist.value = list
  saveWishlist()
  dragIndex.value = -1
}

function updateChart() {
  if (chartInstance) {
    const cityData = popularCities.map(city => {
      let itemStyle = { color: '#6b7280' }
      let symbolSize = 8

      if (wishlist.value.some(w => w.name === city.name)) {
        itemStyle = { color: '#eab308' }
        symbolSize = 12
      }

      return {
        name: city.name,
        value: [city.lng, city.lat],
        itemStyle,
        symbolSize,
        label: {
          show: symbolSize > 8,
          formatter: city.name,
          position: 'right',
          color: '#eab308',
          fontSize: 10
        }
      }
    })

    chartInstance.setOption({
      series: [{
        data: cityData
      }]
    })
  }
}

async function saveWishlist() {
  try {
    await fetch('http://localhost:8001/config/world_wishlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ wishlist: wishlist.value })
    })
  } catch (e) {
    console.error('Failed to save world wishlist:', e)
  }
}

async function loadWishlist() {
  try {
    const res = await fetch('http://localhost:8001/config/world_wishlist')
    wishlist.value = await res.json()
  } catch (e) {
    console.error('Failed to load world wishlist:', e)
  }
}

// Expose for parent
defineExpose({ toggleWishlist })

// Lifecycle
onMounted(async () => {
  await loadWishlist()
  await nextTick()
  
  // Try loading world map GeoJSON from multiple sources
  const sources = [
    '/world.json',  // Local file in public directory
    'https://raw.githubusercontent.com/apache/echarts-website/asf-site/examples/data/asset/geo/world.json',
  ]
  
  let loaded = false
  for (const url of sources) {
    try {
      console.log(`[WorldMap] Trying to load from: ${url}`)
      const response = await fetch(url)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const worldGeoJson = await response.json()
      echarts.registerMap('world', worldGeoJson)
      console.log('[WorldMap] Map data loaded successfully')
      initChart()
      loaded = true
      break
    } catch (e) {
      console.warn(`[WorldMap] Failed to load from ${url}:`, e.message)
    }
  }
  
  if (!loaded) {
    console.error('[WorldMap] All sources failed')
  }
})

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

watch(() => props.fullscreen, async () => {
  await nextTick()
  if (chartInstance) {
    setTimeout(() => {
      chartInstance.resize()
    }, 100)
  }
})
</script>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}
</style>
