/**
 * API base resolution.
 *
 * Desktop (packaged) and dev both talk to 127.0.0.1:8001. But a phone
 * on the LAN loading this app from the host machine must call the API
 * on *that* host, not on its own loopback — so when the page is served
 * from anything other than localhost, derive the API origin from the
 * page's own hostname. This is what makes LAN/PWA access work at all.
 */
const LOCAL_HOSTS = ['localhost', '127.0.0.1', '']

export const API_BASE = (() => {
  if (import.meta.env.VITE_API_BASE) return import.meta.env.VITE_API_BASE
  const host = typeof window !== 'undefined' ? window.location.hostname : ''
  if (LOCAL_HOSTS.includes(host)) return 'http://localhost:8001'
  return `${window.location.protocol}//${host}:8001`
})()

export default API_BASE
