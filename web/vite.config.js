import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/index': {
        target: 'http://localhost:8001',
        changeOrigin: true
      },
      '/config': {
        target: 'http://localhost:8001',
        changeOrigin: true
      },
      '/system': {
        target: 'http://localhost:8001',
        changeOrigin: true
      },
      '/files': {
        target: 'http://localhost:8001',
        changeOrigin: true
      },
      '/search': {
        target: 'http://localhost:8001',
        changeOrigin: true
      },
      '/travel': {
        target: 'http://localhost:8001',
        changeOrigin: true
      }
    }
  },
  root: '.',
  base: '/',
})
