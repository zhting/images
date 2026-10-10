/** Cleanup assistant: categories, preselection, trash with undo, keep. */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))
vi.mock('../composables/useToast', () => ({ toast: vi.fn() }))

import axios from 'axios'
import { toast } from '../composables/useToast'
import Cleanup from '../views/Cleanup.vue'

const it_ = (p, extra = {}) => ({ file_path: p, basename: p.split('/').pop(), captured_time: 1700000000, tag: 'photo', favorite: false, size: 1048576, sharpness: 200, brightness: 120, ...extra })

const payload = () => ({
  total_count: 4, total_bytes: 4 * 1048576, hash_pending: 0, quality: { state: 'running', pending: 7, done: 10 },
  categories: [
    { kind: 'duplicates', label: '重复照片', count: 1, bytes: 1048576, preselect: true, truncated: false,
      groups: [{ keep: '/a/1.jpg', suggest: ['/a/backup/1.jpg'], items: [it_('/a/1.jpg'), it_('/a/backup/1.jpg')] }] },
    { kind: 'bursts', label: '连拍', count: 0, bytes: 0, preselect: true, truncated: false, groups: [] },
    { kind: 'accidental', label: '误拍', count: 0, bytes: 0, preselect: true, truncated: false, items: [] },
    { kind: 'blurry', label: '模糊照片', count: 2, bytes: 2 * 1048576, preselect: false, truncated: false,
      items: [it_('/q/a.jpg', { sharpness: 9.4 }), it_('/q/b.jpg', { sharpness: 20 })] },
    { kind: 'screenshots', label: '旧截图', count: 1, bytes: 1048576, preselect: false, truncated: false,
      items: [it_('/s/1.png', { tag: 'screenshot', text: '订单号 123' })] },
    { kind: 'large_videos', label: '大视频', count: 0, bytes: 0, preselect: false, truncated: false, items: [] },
  ],
})

const setup = async (query = {}) => {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/cleanup', component: Cleanup }] })
  router.push({ path: '/cleanup', query })
  await router.isReady()
  const w = mount(Cleanup, { global: { plugins: [router], stubs: { PhotoViewer: true } } })
  await flushPromises()
  return { w, router }
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  axios.get.mockReset(); axios.post.mockReset(); toast.mockReset()
  axios.get.mockResolvedValue({ data: payload() })
  axios.post.mockResolvedValue({ data: {} })
})

describe('Cleanup', () => {
  it('summarises categories and preselects only the safe ones', async () => {
    const { w } = await setup()
    expect(w.text()).toContain('可释放约 4.0 MB')
    expect(w.text()).toContain('还剩 7 张')
    expect(w.vm.tab).toBe('duplicates')                 // first category with suggestions
    expect([...w.vm.selected]).toEqual(['/a/backup/1.jpg'])
    expect(w.text()).toContain('保留')                   // keeper badge
    expect(w.text()).toContain('已选 1 项 · 1.0 MB')
  })

  it('moves the selection to the recycle bin, with undo', async () => {
    const { w } = await setup()
    const btn = w.findAll('button').find(b => b.text() === '移入回收站')
    await btn.trigger('click'); await flushPromises()
    expect(axios.post).toHaveBeenCalledWith('/api/files/trash', { file_paths: ['/a/backup/1.jpg'] })
    expect(axios.get).toHaveBeenCalledTimes(2)           // reloaded
    const [msg, opts] = toast.mock.calls[0]
    expect(msg).toContain('1 项')
    await opts.onAction(); await flushPromises()
    expect(axios.post).toHaveBeenCalledWith('/api/files/restore', { file_paths: ['/a/backup/1.jpg'] })
  })

  it('lets the user pick blurry photos and stop suggesting them', async () => {
    const { w } = await setup({ tab: 'blurry' })
    expect(w.vm.tab).toBe('blurry')
    expect(w.text()).toContain('清晰度 9')
    expect(w.text()).not.toContain('已选')               // nothing preselected here
    await w.findAll('button').find(b => b.text() === '全选').trigger('click')
    expect(w.text()).toContain('已选 2 项 · 2.0 MB')
    await w.findAll('button').find(b => b.text() === '不再建议').trigger('click'); await flushPromises()
    expect(axios.post).toHaveBeenCalledWith('/api/cleanup/keep', { kind: 'blurry', file_paths: ['/q/a.jpg', '/q/b.jpg'] })
  })

  it('shows screenshot text and an all-clear state', async () => {
    const { w } = await setup({ tab: 'screenshots' })
    expect(w.text()).toContain('订单号 123')
    await w.findAll('[role=tab]').find(b => b.text().includes('大视频')).trigger('click')
    expect(w.text()).toContain('这一类没有需要清理的')
  })
})
