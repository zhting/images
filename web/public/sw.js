/* Shell-only service worker.
 *
 * Deliberately does NOT cache /files/* — photos are large and private,
 * and the backend already serves thumbnails as immutable and originals
 * with ETags, so the browser HTTP cache covers them. Duplicating them
 * into a service-worker cache would bloat storage and leave private
 * imagery lying around after the app is closed.
 */
const SHELL = 'deep-photo-shell-v1'

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(['/', '/manifest.webmanifest'])))
  self.skipWaiting()
})

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== SHELL).map((k) => caches.delete(k))))
  )
  self.clients.claim()
})

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url)
  // Never touch API or media traffic.
  if (e.request.method !== 'GET') return
  if (url.port === '8001' || url.pathname.startsWith('/files/')) return

  // Network-first for the shell so updates land without a hard reload.
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        const copy = res.clone()
        caches.open(SHELL).then((c) => c.put(e.request, copy)).catch(() => {})
        return res
      })
      .catch(() => caches.match(e.request).then((r) => r || caches.match('/')))
  )
})
