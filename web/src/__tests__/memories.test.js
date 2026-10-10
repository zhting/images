/** Memories page and the route-playback engine behind trip replays. */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))
vi.mock('../composables/useToast', () => ({ toast: vi.fn() }))

import axios from 'axios'
import Memories from '../views/Memories.vue'
import { createPlayback, legPoints, distanceKm, legDuration } from '../lib/routePlayback'

const KM = { lat: 25.04, lon: 102.71, highlights: ['/a', '/b'] }
const DL = { lat: 25.61, lon: 100.27, highlights: ['/c'] }
const TK = { lat: 35.68, lon: 139.69, highlights: [] }

describe('route playback', () => {
  it('measures distance and bows long legs into an arc', () => {
    expect(distanceKm([KM.lat, KM.lon], [DL.lat, DL.lon])).toBeGreaterThan(240)
    expect(distanceKm([KM.lat, KM.lon], [DL.lat, DL.lon])).toBeLessThan(260)
    expect(legPoints([30, 120], [30.1, 120.1])).toHaveLength(2)            // short: straight
    const arc = legPoints([30.25, 120.16], [TK.lat, TK.lon])
    expect(arc.length).toBeGreaterThan(10)
    expect(arc[0]).toEqual([30.25, 120.16])
    expect(arc.at(-1)[0]).toBeCloseTo(TK.lat)
    // across the date line the leg takes the short way
    const pac = legPoints([21.3, -157.8], [35.68, 139.69])
    expect(Math.abs(pac.at(-1)[1] - -157.8)).toBeLessThan(180)
  })

  it('dwells at a stop, travels, then arrives at the next stop', () => {
    const pb = createPlayback([KM, DL, TK], { dwellPhotos: s => s.highlights.length })
    let st = pb.state()
    expect(st).toMatchObject({ stop: 0, phase: 'dwell', photoIndex: 0, done: false })
    expect(st.position).toEqual([KM.lat, KM.lon])
    pb.advance(1200)                       // second photo of the first stop
    expect(pb.state().photoIndex).toBe(1)
    pb.advance(1100 + legDuration(250) / 2) // half way to Dali
    st = pb.state()
    expect(st.phase).toBe('move')
    expect(st.position[1]).toBeLessThan(KM.lon)
    expect(st.position[1]).toBeGreaterThan(DL.lon)
    expect(st.trail.length).toBeGreaterThanOrEqual(2)
    pb.advance(legDuration(250))
    expect(pb.state()).toMatchObject({ stop: 1, phase: 'dwell' })
    expect(pb.stopStarts).toHaveLength(3)
    expect(pb.stopStarts[0]).toBe(0)
  })

  it('speeds up, seeks and finishes', () => {
    const pb = createPlayback([KM, DL, TK], { dwellPhotos: s => s.highlights.length })
    pb.seek(2)
    expect(pb.state()).toMatchObject({ stop: 2, phase: 'dwell' })
    expect(pb.state().fraction).toBeCloseTo(pb.stopStarts[2])
    pb.setSpeed(4)
    pb.advance(10000)
    expect(pb.done).toBe(true)
    expect(pb.state().fraction).toBe(1)
    pb.restart()
    expect(pb.state()).toMatchObject({ stop: 0, done: false })
  })

  it('handles a single-stop trip', () => {
    const pb = createPlayback([KM])
    expect(pb.route).toEqual([[KM.lat, KM.lon]])
    pb.advance(5000)
    expect(pb.done).toBe(true)
  })
})

const memories = {
  on_this_week: [{ year: 2025, years_ago: 1, start: 1752019200, end: 1752624000, count: 12, cover: '/c.jpg',
    photos: [{ file_path: '/c.jpg', tag: 'photo' }] }],
  trips: [
    { id: 't1', title: 'Dali · Kunming', start: 1752112800, end: 1752552000, days: 6, cities: ['Dali', 'Kunming'],
      countries: ['中国'], abroad: false, photo_count: 12, distance_km: 390, cover: '/c.jpg', stop_count: 2,
      path: [[25.04, 102.71], [25.61, 100.27]] },
    { id: 't2', title: 'Tokyo', start: 1759284000, end: 1759460000, days: 3, cities: ['Tokyo'],
      countries: ['日本'], abroad: true, photo_count: 5, distance_km: 0, cover: '/t.jpg', stop_count: 1,
      path: [[35.68, 139.69]] },
  ],
  years: [{ year: 2025, count: 47, cover: '/c.jpg', places: ['Hangzhou'], trip_count: 2 }],
}

const mountPage = async () => {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/memories', component: Memories }, { path: '/:p(.*)*', component: { template: '<div/>' } }] })
  router.push('/memories')
  await router.isReady()
  const w = mount(Memories, { global: { plugins: [router], stubs: { PhotoViewer: true } } })
  await flushPromises()
  return w
}

beforeEach(() => { axios.get.mockReset() })

describe('Memories page', () => {
  it('shows this week, trips with replay links and years', async () => {
    axios.get.mockResolvedValue({ data: memories })
    const w = await mountPage()
    expect(axios.get).toHaveBeenCalledWith('/api/memories')
    expect(w.text()).toContain('1 年前的这周')
    expect(w.text()).toContain('Dali · Kunming')
    expect(w.text()).toContain('境外')
    const links = w.findAll('a').map(a => a.attributes('href'))
    expect(links).toContain('/memories/trips/t1')
    expect(links).toContain('/memories/year/2025')
    // one sketch for the two-stop trip, none for the single-stop one
    expect(w.findAll('svg polyline')).toHaveLength(1)
  })

  it('fits the route sketch in its box', async () => {
    axios.get.mockResolvedValue({ data: memories })
    const w = await mountPage()
    const pts = w.vm.miniPoints([[25.04, 102.71], [25.61, 100.27], [26.87, 100.23]])
    for (const [x, y] of pts) {
      expect(x).toBeGreaterThanOrEqual(7); expect(x).toBeLessThanOrEqual(93)
      expect(y).toBeGreaterThanOrEqual(7); expect(y).toBeLessThanOrEqual(53)
    }
  })

  it('explains how trips are found when there are none', async () => {
    axios.get.mockResolvedValue({ data: { ...memories, trips: [], on_this_week: [] } })
    const w = await mountPage()
    expect(w.text()).toContain('还没有识别出旅行')
    expect(w.text()).not.toContain('那年这周')
  })
})
