/**
 * Route playback for a trip: a marker travels stop to stop along the
 * route, pausing at each stop while its photos are shown.
 *
 * Pure timing/geometry — no Leaflet, no timers — so it is easy to test.
 * The page calls `advance(ms)` from requestAnimationFrame and reads
 * `state()` to place the marker, grow the travelled line and pick the
 * photo to show.
 *
 *   const pb = createPlayback(stops, { dwellPhotos: s => s.highlights.length })
 *   pb.advance(16)  ->  pb.state()  // { stop, phase, position, trail, photoIndex, done, fraction }
 */

const R = 6371

export function distanceKm(a, b) {
  const toRad = (d) => (d * Math.PI) / 180
  const dLat = toRad(b[0] - a[0])
  const dLon = toRad(b[1] - a[1])
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a[0])) * Math.cos(toRad(b[0])) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)))
}

/**
 * Points from a to b. Long legs (flights) bow out into an arc so they read
 * as travel rather than a ruler line; short legs stay straight. Longitudes
 * are unwrapped so a leg across the date line takes the short way.
 */
export function legPoints(a, b, n = 32) {
  let [lat2, lon2] = b
  if (lon2 - a[1] > 180) lon2 -= 360
  else if (a[1] - lon2 > 180) lon2 += 360
  const km = distanceKm(a, b)
  const pts = []
  if (km < 300) {
    pts.push([a[0], a[1]], [lat2, lon2])
    return pts
  }
  const dLat = lat2 - a[0]
  const dLon = lon2 - a[1]
  const bow = 0.18
  const c = [(a[0] + lat2) / 2 + dLon * bow, (a[1] + lon2) / 2 - dLat * bow]
  for (let i = 0; i <= n; i++) {
    const t = i / n
    const u = 1 - t
    pts.push([u * u * a[0] + 2 * u * t * c[0] + t * t * lat2, u * u * a[1] + 2 * u * t * c[1] + t * t * lon2])
  }
  return pts
}

/** Cumulative-length lookup so the marker moves at a steady pace. */
function measure(pts) {
  const cum = [0]
  for (let i = 1; i < pts.length; i++) {
    const dx = pts[i][0] - pts[i - 1][0]
    const dy = pts[i][1] - pts[i - 1][1]
    cum.push(cum[i - 1] + Math.hypot(dx, dy))
  }
  return cum
}

function pointAt(pts, cum, f) {
  const total = cum[cum.length - 1]
  if (total === 0 || f <= 0) return { point: pts[0], upTo: 0 }
  if (f >= 1) return { point: pts[pts.length - 1], upTo: pts.length - 1 }
  const target = f * total
  let i = 1
  while (i < cum.length - 1 && cum[i] < target) i++
  const seg = cum[i] - cum[i - 1] || 1
  const t = (target - cum[i - 1]) / seg
  const p = [pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * t, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * t]
  return { point: p, upTo: i - 1 }
}

/** Travel time for a leg: longer legs take longer, but not linearly. */
export function legDuration(km) {
  return Math.min(3200, Math.max(900, 700 + 420 * Math.log2(1 + km / 20)))
}

export const PHOTO_MS = 1100

export function createPlayback(stops, { dwellPhotos = () => 0, speed = 1 } = {}) {
  const coords = stops.map((s) => [s.lat, s.lon])
  const legs = coords.slice(1).map((b, i) => {
    const pts = legPoints(coords[i], b)
    return { pts, cum: measure(pts), ms: legDuration(distanceKm(coords[i], b)) }
  })
  const dwells = stops.map((s) => Math.max(1400, PHOTO_MS * Math.min(4, dwellPhotos(s) || 0)))

  // Phase timeline: dwell(0), move(0->1), dwell(1), ..., dwell(last)
  const phases = []
  stops.forEach((_, i) => {
    phases.push({ kind: 'dwell', stop: i, ms: dwells[i] })
    if (i < legs.length) phases.push({ kind: 'move', stop: i, ms: legs[i].ms })
  })
  const totalMs = phases.reduce((a, p) => a + p.ms, 0)
  // Where each stop's arrival sits on a 0..1 progress bar.
  const stopStarts = []
  phases.reduce((acc, p) => {
    if (p.kind === 'dwell') stopStarts.push(totalMs ? acc / totalMs : 0)
    return acc + p.ms
  }, 0)

  let phase = 0
  let elapsed = 0 // within the current phase
  let rate = speed

  const route = []
  legs.forEach((l, i) => route.push(...(i ? l.pts.slice(1) : l.pts)))
  if (!legs.length && coords.length) route.push(coords[0])

  // Trail up to the start of leg i (for redrawing after a seek).
  const trailBefore = (legIdx) => {
    const out = coords.length ? [coords[0]] : []
    for (let i = 0; i < legIdx; i++) out.push(...legs[i].pts.slice(1))
    return out
  }

  const api = {
    route,
    totalMs,
    stopStarts,
    get speed() { return rate },
    setSpeed(s) { rate = s },
    advance(ms) {
      if (api.done) return
      elapsed += ms * rate
      while (phase < phases.length && elapsed >= phases[phase].ms) {
        elapsed -= phases[phase].ms
        phase++
      }
      if (phase >= phases.length) {
        phase = phases.length - 1
        elapsed = phases[phase].ms
      }
    },
    get done() {
      return phase === phases.length - 1 && elapsed >= phases[phase].ms
    },
    /** Jump to the moment the marker arrives at stop i. */
    seek(i) {
      const idx = Math.max(0, Math.min(stops.length - 1, i))
      phase = idx * 2
      elapsed = 0
    },
    restart() { phase = 0; elapsed = 0 },
    state() {
      const p = phases[phase]
      if (!p) return { stop: 0, phase: 'dwell', position: null, trail: [], photoIndex: 0, done: true, fraction: 1 }
      const f = Math.min(1, elapsed / p.ms)
      let position
      let trail
      if (p.kind === 'move') {
        const leg = legs[p.stop]
        const at = pointAt(leg.pts, leg.cum, f)
        position = at.point
        trail = trailBefore(p.stop).concat(leg.pts.slice(1, at.upTo + 1), [at.point])
      } else {
        position = coords[p.stop]
        trail = trailBefore(p.stop)
      }
      const before = phases.slice(0, phase).reduce((a, x) => a + x.ms, 0)
      const n = Math.min(4, dwellPhotos(stops[p.stop]) || 0)
      return {
        stop: p.stop,
        phase: p.kind,
        position,
        trail,
        photoIndex: p.kind === 'dwell' && n ? Math.min(n - 1, Math.floor(f * n)) : 0,
        done: api.done,
        fraction: totalMs ? (before + elapsed) / totalMs : 1,
      }
    },
  }
  return api
}
