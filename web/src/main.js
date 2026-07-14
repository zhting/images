import { createApp } from 'vue'
import './style.css'
import './composables/useTheme'  // applies the persisted theme class
import App from './App.vue'
import router from './router'

createApp(App).use(router).mount('#app')
