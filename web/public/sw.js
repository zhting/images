/* Shell-only service worker.
 *
 * Deliberately does NOT cache API traffic (/api/*) — photos are large and
 * private, and the backend already serves thumbnails as immutable and
 * originals with ETags, so the browser HTTP cache covers them. Duplicating
 * them into a service-worker cache would bloat storage and leave private
 * imagery lying around after the app is closed.
 */
const SHELL = 'deep-photo-shell-v2'

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
  const req = e.request
  const url = new URL(req.url)
  if (req.method !== 'GET') return
  // Only same-origin app-shell files. API calls and anything cross-origin
  // (map tiles) go straight to the network.
  if (url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return

  // Network-first so updates land without a hard reload.
  e.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone()
          caches.open(SHELL).then((c) => c.put(req, copy)).catch(() => {})
        }
        return res
      })
      .catch(async () => {
        const cached = await caches.match(req)
        if (cached) return cached
        // Fall back to the app shell only for page navigations. Answering a
        // failed *script* or *stylesheet* request with index.html is what
        // produced "Unexpected token '<'" on every page whenever a
        // resource could not be fetched.
        if (req.mode === 'navigate') return caches.match('/')
        return Response.error()
      })
  )
})
