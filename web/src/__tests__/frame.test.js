/** Full-screen photo frame: sources, timing, keys, skipping broken files. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

import axios from 'axios'
import Frame from '../views/Frame.vue'

const items = [
  { file_path: '/p/1.jpg', captured_time: 1757500000, place: '大理', favorite: false },
  { file_path: '/p/broken.jpg', captured_time: 1757600000, place: '', favorite: false },
  { file_path: '/p/3.jpg', captured_time: 1757700000, place: 'Tokyo · 日本', favorite: true },
]

// jsdom never loads images: resolve (or fail) them on the next tick.
class FakeImage {
  set src(v) {
    this._src = v
    setTimeout(() => (v.includes('broken') ? this.onerror?.(new Error('404')) : this.onload?.()), 0)
  }
  get src() { return this._src }
  decode() { return Promise.resolve() }
}

const settle = async () => { for (let i = 0; i < 6; i++) { await vi.advanceTimersByTimeAsync(1); await flushPromises() } }

const setup = async (query = {}) => {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/frame', component: Frame }, { path: '/timeline', component: { template: '<div/>' } }] })
  router.push({ path: '/frame', query })
  await router.isReady()
  const w = mount(Frame, { global: { plugins: [router] }, attachTo: document.body })
  await settle()
  return { w, router }
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal('Image', FakeImage)
  localStorage.clear()
  axios.get.mockReset()
  axios.get.mockImplementation((url) => url.endsWith('/frame/sources')
    ? Promise.resolve({ data: { albums: [{ id: 2, name: '旅行', count: 3 }], people: [], trips: [], years: [2025] } })
    : Promise.resolve({ data: { label: '旅行', items: items.map(i => ({ ...i })), total: 3 } }))
})
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); document.body.innerHTML = '' })

describe('Frame', () => {
  it('loads the requested source and shows the first photo with its place', async () => {
    const { w } = await setup({ source: 'album:2' })
    const call = axios.get.mock.calls.find(c => c[0].endsWith('/frame/photos'))
    expect(call[1].params.source).toBe('album:2')
    expect(w.vm.state).toBe('playing')
    expect(w.vm.index).toBe(0)
    expect(w.text()).toContain('旅行 · 1/3')
    expect(w.text()).toContain('大理')
    expect(w.find('img[src*="size=preview"]').exists()).toBe(true)
  })

  it('advances on the interval and skips files that fail to load', async () => {
    const { w } = await setup()
    expect(w.vm.index).toBe(0)
    await vi.advanceTimersByTimeAsync(10_000); await settle()
    expect(w.vm.index).toBe(2)                     // /p/broken.jpg skipped
    expect(w.text()).toContain('Tokyo · 日本')
  })

  it('pauses with space and steps with the arrow keys', async () => {
    const { w } = await setup()
    window.dispatchEvent(new KeyboardEvent('keydown', { key: ' ' }))
    expect(w.vm.paused).toBe(true)
    await vi.advanceTimersByTimeAsync(30_000); await settle()
    expect(w.vm.index).toBe(0)                     // paused: no auto-advance
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft' })); await settle()
    expect(w.vm.index).toBe(2)                     // wraps backwards
  })

  it('remembers display settings in this browser', async () => {
    const { w } = await setup()
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'c' })); await flushPromises()
    w.vm.settings.interval = 30; await flushPromises()
    expect(JSON.parse(localStorage.getItem('deepphoto.frame'))).toMatchObject({ clock: false, interval: 30 })
  })

  it('says so when a source has nothing to show, and exits', async () => {
    axios.get.mockImplementation((url) => url.endsWith('/frame/sources')
      ? Promise.resolve({ data: {} }) : Promise.resolve({ data: { label: '收藏', items: [], total: 0 } }))
    const { w, router } = await setup({ source: 'favorites' })
    expect(w.text()).toContain('没有可放映的照片')
    await w.findAll('button').find(b => b.text() === '退出').trigger('click'); await flushPromises()
    expect(router.currentRoute.value.path).toBe('/timeline')
  })
})
