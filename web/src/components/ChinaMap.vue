<template>
  <div class="w-full h-full flex bg-[#1f2937]">
    <!-- ECharts Map Container -->
    <div class="flex-1 relative h-full">
      <!-- Map -->
      <div ref="chartContainer" class="absolute inset-0 w-full h-full"></div>
    </div>

    <!-- Wishlist Sidebar removed, now managed in Places.vue -->
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  places: {
    type: Array,
    default: () => []
  },
  wishlist: {
    type: Array,
    default: () => []
  },
  fullscreen: {
    type: Boolean,
    default: false
  }
})

// Global cache for GeoJSON to prevent re-fetching
let geoJsonCache = null

const emit = defineEmits(['place-click', 'update:fullscreen'])

// Refs
const chartContainer = ref(null)
let chartInstance = null

// Popular tourist cities with lat/lng
const popularCities = [
  { name: '北京', province: '北京', lng: 116.46, lat: 39.92 },
  { name: '上海', province: '上海', lng: 121.48, lat: 31.22 },
  { name: '天津', province: '天津', lng: 117.2, lat: 39.13 },
  { name: '重庆', province: '重庆', lng: 106.54, lat: 29.59 },
  { name: '承德', province: '河北', lng: 117.93, lat: 40.95 },
  { name: '保定', province: '河北', lng: 115.48, lat: 38.85 },
  { name: '秦皇岛', province: '河北', lng: 119.6, lat: 39.93 },
  { name: '大同', province: '山西', lng: 113.3, lat: 40.08 },
  { name: '平遥', province: '山西', lng: 112.18, lat: 37.2 },
  { name: '呼和浩特', province: '内蒙古', lng: 111.67, lat: 40.82 },
  { name: '包头', province: '内蒙古', lng: 109.82, lat: 40.65 },
  { name: '呼伦贝尔', province: '内蒙古', lng: 119.76, lat: 49.2 },
  { name: '沈阳', province: '辽宁', lng: 123.43, lat: 41.8 },
  { name: '大连', province: '辽宁', lng: 121.63, lat: 38.92 },
  { name: '长春', province: '吉林', lng: 125.32, lat: 43.82 },
  { name: '吉林', province: '吉林', lng: 126.55, lat: 43.83 },
  { name: '哈尔滨', province: '黑龙江', lng: 126.53, lat: 45.8 },
  { name: '漠河', province: '黑龙江', lng: 122.52, lat: 52.97 },
  { name: '南京', province: '江苏', lng: 118.78, lat: 32.07 },
  { name: '苏州', province: '江苏', lng: 120.58, lat: 31.3 },
  { name: '杭州', province: '浙江', lng: 120.15, lat: 30.28 },
  { name: '宁波', province: '浙江', lng: 121.55, lat: 29.87 },
  { name: '乌镇', province: '浙江', lng: 120.48, lat: 30.74 },
  { name: '黄山', province: '安徽', lng: 118.18, lat: 29.72 },
  { name: '厦门', province: '福建', lng: 118.1, lat: 24.46 },
  { name: '福州', province: '福建', lng: 119.27, lat: 26.08 },
  { name: '庐山', province: '江西', lng: 115.97, lat: 29.45 },
  { name: '婺源', province: '江西', lng: 117.86, lat: 29.25 },
  { name: '济南', province: '山东', lng: 117.0, lat: 36.65 },
  { name: '青岛', province: '山东', lng: 120.38, lat: 36.07 },
  { name: '泰山', province: '山东', lng: 117.09, lat: 36.25 },
  { name: '洛阳', province: '河南', lng: 112.44, lat: 34.62 },
  { name: '开封', province: '河南', lng: 114.35, lat: 34.8 },
  { name: '武汉', province: '湖北', lng: 114.3, lat: 30.58 },
  { name: '三峡', province: '湖北', lng: 110.42, lat: 30.97 },
  { name: '张家界', province: '湖南', lng: 110.47, lat: 29.12 },
  { name: '凤凰古城', province: '湖南', lng: 109.6, lat: 27.95 },
  { name: '广州', province: '广东', lng: 113.23, lat: 23.16 },
  { name: '深圳', province: '广东', lng: 114.07, lat: 22.62 },
  { name: '珠海', province: '广东', lng: 113.52, lat: 22.3 },
  { name: '三亚', province: '海南', lng: 109.51, lat: 18.25 },
  { name: '海口', province: '海南', lng: 110.35, lat: 20.02 },
  { name: '成都', province: '四川', lng: 104.07, lat: 30.67 },
  { name: '九寨沟', province: '四川', lng: 103.92, lat: 33.1 },
  { name: '稻城亚丁', province: '四川', lng: 100.3, lat: 28.47 },
  { name: '贵阳', province: '贵州', lng: 106.7, lat: 26.57 },
  { name: '黄果树', province: '贵州', lng: 105.43, lat: 25.95 },
  { name: '昆明', province: '云南', lng: 102.73, lat: 25.04 },
  { name: '大理', province: '云南', lng: 100.27, lat: 25.59 },
  { name: '丽江', province: '云南', lng: 100.23, lat: 26.88 },
  { name: '香格里拉', province: '云南', lng: 99.7, lat: 27.82 },
  { name: '拉萨', province: '西藏', lng: 91.11, lat: 29.65 },
  { name: '林芝', province: '西藏', lng: 94.37, lat: 29.65 },
  { name: '西安', province: '陕西', lng: 108.95, lat: 34.27 },
  { name: '延安', province: '陕西', lng: 109.49, lat: 36.58 },
  { name: '兰州', province: '甘肃', lng: 103.73, lat: 36.03 },
  { name: '敦煌', province: '甘肃', lng: 94.66, lat: 40.14 },
  { name: '张掖', province: '甘肃', lng: 100.44, lat: 38.93 },
  { name: '西宁', province: '青海', lng: 101.78, lat: 36.62 },
  { name: '青海湖', province: '青海', lng: 100.47, lat: 36.6 },
  { name: '银川', province: '宁夏', lng: 106.27, lat: 38.47 },
  { name: '乌鲁木齐', province: '新疆', lng: 87.68, lat: 43.77 },
  { name: '喀什', province: '新疆', lng: 75.99, lat: 39.47 },
  { name: '吐鲁番', province: '新疆', lng: 89.19, lat: 42.95 },
  { name: '香港', province: '香港', lng: 114.17, lat: 22.28 },
  { name: '澳门', province: '澳门', lng: 113.54, lat: 22.19 },
  { name: '台北', province: '台湾', lng: 121.52, lat: 25.05 },
  { name: '高雄', province: '台湾', lng: 120.3, lat: 22.62 },
]

// Computed
const visitedProvinces = computed(() => {
  const set = new Set()
  props.places.forEach(place => {
    if (place.province) set.add(normalizeProvince(place.province))
  })
  return set
})

const visitedCities = computed(() => {
  const set = new Set()
  props.places.forEach(place => {
    if (place.city) set.add(place.city)
    if (place.name) set.add(place.name.split(',')[0].trim())
  })
  return set
})

// Functions
function normalizeProvince(name) {
  if (!name) return ''
  // Map to GeoJSON full names used by DataV China map
  // First check if it's already a full GeoJSON name
  const geoNames = [
    '北京市','天津市','河北省','山西省','内蒙古自治区','辽宁省','吉林省',
    '黑龙江省','上海市','江苏省','浙江省','安徽省','福建省','江西省',
    '山东省','河南省','湖北省','湖南省','广东省','广西壮族自治区','海南省',
    '重庆市','四川省','贵州省','云南省','西藏自治区','陕西省','甘肃省',
    '青海省','宁夏回族自治区','新疆维吾尔自治区','台湾省',
    '香港特别行政区','澳门特别行政区'
  ]
  if (geoNames.includes(name)) return name
  
  // Map short names to GeoJSON full names
  const shortToFull = {
    '北京': '北京市', '天津': '天津市', '上海': '上海市', '重庆': '重庆市',
    '河北': '河北省', '山西': '山西省', '辽宁': '辽宁省', '吉林': '吉林省',
    '黑龙江': '黑龙江省', '江苏': '江苏省', '浙江': '浙江省', '安徽': '安徽省',
    '福建': '福建省', '江西': '江西省', '山东': '山东省', '河南': '河南省',
    '湖北': '湖北省', '湖南': '湖南省', '广东': '广东省', '海南': '海南省',
    '四川': '四川省', '贵州': '贵州省', '云南': '云南省', '陕西': '陕西省',
    '甘肃': '甘肃省', '青海': '青海省', '台湾': '台湾省',
    '内蒙古': '内蒙古自治区', '广西': '广西壮族自治区', '西藏': '西藏自治区',
    '宁夏': '宁夏回族自治区', '新疆': '新疆维吾尔自治区',
    '香港': '香港特别行政区', '澳门': '澳门特别行政区',
  }
  if (shortToFull[name]) return shortToFull[name]
  
  // Try adding common suffixes
  if (!name.endsWith('省') && !name.endsWith('市') && !name.endsWith('区')) {
    if (geoNames.includes(name + '省')) return name + '省'
    if (geoNames.includes(name + '市')) return name + '市'
  }
  return name
}

function initChart() {
  if (!chartContainer.value) return

  // Dispose of existing instance before creating a new one to prevent warnings
  const existingInstance = echarts.getInstanceByDom(chartContainer.value)
  if (existingInstance) {
    existingInstance.dispose()
  }

  chartInstance = echarts.init(chartContainer.value)

  // Get visited provinces for map coloring
  const visitedProvinceNames = Array.from(visitedProvinces.value)

  // Prepare city scatter data - use distinct colors from provinces
  const cityData = popularCities.map(city => {
    const isWishlist = props.wishlist.some(w => w.name === city.name)
    const isVisited = visitedCities.value.has(city.name)

    let itemStyle, symbolSize, labelShow, labelColor

    if (isWishlist) {
      // Wishlist: gold star
      itemStyle = { color: '#f59e0b', borderColor: '#fbbf24', borderWidth: 2 }
      symbolSize = 12
      labelShow = true
      labelColor = '#fbbf24'
    } else if (isVisited) {
      // Visited city: bright cyan (distinct from province teal)
      itemStyle = { color: '#22d3ee', borderColor: '#fff', borderWidth: 1.5 }
      symbolSize = 14
      labelShow = true
      labelColor = '#67e8f9'
    } else {
      // Unvisited: dim gray dot
      itemStyle = { color: '#4b5563' }
      symbolSize = 6
      labelShow = false
      labelColor = '#9ca3af'
    }

    return {
      name: city.name,
      value: [city.lng, city.lat, city.province],
      itemStyle,
      symbolSize,
      label: {
        show: labelShow,
        formatter: city.name,
        position: 'right',
        color: labelColor,
        fontSize: 11,
        fontWeight: isVisited ? 'bold' : 'normal',
        textShadowColor: '#000',
        textShadowBlur: 3
      }
    }
  })

  const option = {
    backgroundColor: '#1f2937',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(30,30,50,0.95)',
      borderColor: '#555',
      textStyle: { color: '#fff' },
      formatter: function(params) {
        if (params.seriesType === 'scatter') {
          const city = popularCities.find(c => c.name === params.name)
          const isVisited = visitedCities.value.has(params.name)
          const isWishlist = props.wishlist.some(w => w.name === params.name)
          let statusIcon = '⚪'
          let statusText = '未访问'
          if (isVisited) { statusIcon = '📸'; statusText = '已访问（有照片）' }
          else if (isWishlist) { statusIcon = '⭐'; statusText = '愿望清单' }
          return `<b>${params.name}</b><br/>省份: ${city?.province}<br/>${statusIcon} ${statusText}`
        }
        // Province tooltip
        const isVisitedProv = visitedProvinceNames.includes(params.name)
        return `<b>${params.name}</b><br/>${isVisitedProv ? '🟢 有照片记录' : '⚪ 暂无照片'}`
      }
    },
    // Province legend indicator
    visualMap: {
      show: true,
      type: 'piecewise',
      left: 20,
      bottom: 20,
      pieces: [
        { value: 1, label: '有照片的省份', color: '#2d8f7a' },
        { value: 0, label: '暂无照片', color: '#2d3748' },
      ],
      textStyle: { color: '#9ca3af', fontSize: 11 },
      itemWidth: 16,
      itemHeight: 12,
    },
    geo: {
      map: 'china',
      roam: true,
      zoom: 1.2,
      center: [105, 36],
      itemStyle: {
        areaColor: '#2d3748',
        borderColor: '#4a5568',
        borderWidth: 0.8
      },
      emphasis: {
        itemStyle: {
          areaColor: '#3d8a78'
        },
        label: {
          show: true,
          color: '#fff',
          fontSize: 13
        }
      },
      label: {
        show: false
      },
      // Highlight visited provinces with teal green (distinct from city cyan)
      regions: visitedProvinceNames.map(name => ({
        name,
        itemStyle: {
          areaColor: '#2d8f7a',
          borderColor: '#5ef5d0',
          borderWidth: 1.5
        },
        label: {
          show: true,
          color: '#86efac',
          fontSize: 11
        }
      }))
    },
    series: [
      {
        name: '城市',
        type: 'scatter',
        coordinateSystem: 'geo',
        data: cityData,
        itemStyle: {
          shadowBlur: 8,
          shadowColor: 'rgba(0,0,0,0.5)'
        },
        emphasis: {
          scale: 1.6
        }
      }
    ]
  }

  chartInstance.setOption(option)

  // Click handler
  chartInstance.on('click', function(params) {
    if (params.seriesType === 'scatter') {
      const cityName = params.name
      if (visitedCities.value.has(cityName)) {
        emit('place-click', cityName)
      }
    }
  })

  // Resize handler
  window.addEventListener('resize', () => {
    chartInstance?.resize()
  })
}

function toggleFullscreen() {
  emit('update:fullscreen', !props.fullscreen)
}

function updateChart() {
  if (chartInstance) {
    const cityData = popularCities.map(city => {
      const isWishlist = props.wishlist.some(w => w.name === city.name)
      const isVisited = visitedCities.value.has(city.name)

      let itemStyle, symbolSize, labelShow, labelColor

      if (isWishlist) {
        itemStyle = { color: '#f59e0b', borderColor: '#fbbf24', borderWidth: 2 }
        symbolSize = 12
        labelShow = true
        labelColor = '#fbbf24'
      } else if (isVisited) {
        itemStyle = { color: '#22d3ee', borderColor: '#fff', borderWidth: 1.5 }
        symbolSize = 14
        labelShow = true
        labelColor = '#67e8f9'
      } else {
        itemStyle = { color: '#4b5563' }
        symbolSize = 6
        labelShow = false
        labelColor = '#9ca3af'
      }

      return {
        name: city.name,
        value: [city.lng, city.lat, city.province],
        itemStyle,
        symbolSize,
        label: {
          show: labelShow,
          formatter: city.name,
          position: 'right',
          color: labelColor,
          fontSize: 11,
          fontWeight: isVisited ? 'bold' : 'normal',
          textShadowColor: '#000',
          textShadowBlur: 3
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
const handleResize = () => {
  chartInstance?.resize()
}

// Lifecycle
onMounted(async () => {
  await nextTick()
  window.addEventListener('resize', handleResize)
  
  try {
    if (!geoJsonCache) {
      const response = await fetch('/china.json')
      geoJsonCache = await response.json()
    }
    echarts.registerMap('china', geoJsonCache)
    initChart()
    
    // Extra resize to ensure correct dimensions after data load
    setTimeout(() => {
      chartInstance?.resize()
    }, 200)
  } catch (e) {
    console.error('Failed to load China map:', e)
    initChart()
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
})

watch(() => props.places, () => {
  updateChart()
}, { deep: true })

watch(() => props.wishlist, () => {
  updateChart()
}, { deep: true })

watch(() => props.fullscreen, async (newVal) => {
  await nextTick()
  if (chartInstance) {
    setTimeout(() => {
      chartInstance.resize()
    }, 100)
  }
})

// Expose for parent
defineExpose({})
</script>

<style scoped>
</style>
