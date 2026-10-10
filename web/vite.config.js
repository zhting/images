import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// LAN access is opt-in (DEEPPHOTO_LAN=1, same switch as the backend). The
// dev server proxies /api, so binding it to 0.0.0.0 by default would let
// any device on the network read photos through it even while the backend
// itself only listens on loopback.
const lan = process.env.DEEPPHOTO_LAN === '1'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    host: lan ? '0.0.0.0' : '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      // Single prefix: page routes (/travel, /people, ...) are never proxied,
      // so reloading any page serves the app instead of an API 404.
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
  },
  root: '.',
  base: '/',
})
