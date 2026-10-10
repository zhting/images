/** /search page: query in the URL, interpreted-filter chips, text matches. */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))
vi.mock('../composables/useToast', () => ({ toast: vi.fn() }))

import axios from 'axios'
import SearchView from '../views/SearchView.vue'

const response = {
  data: {
    results: [
      { file_path: '/a.jpg', basename: 'a.jpg', score: 0.3, tag: 'photo', match: ['semantic'], snippet: '' },
      { file_path: '/r.png', basename: 'r.png', score: 0.3, tag: 'screenshot', match: ['text'], snippet: '…增值税电子普通发票…' },
    ],
    parsed: {
      text: '日落', chips: [
        { kind: 'time', label: '2025年夏天', token: '去年夏天' },
        { kind: 'place', label: '大理市', token: '大理' },
      ],
    },
    translated_query: 'sunset', ocr: { available: true, state: 'running', pending: 12, done: 30 },
  },
}

const setup = async (q) => {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/search', component: SearchView }] })
  router.push({ path: '/search', query: q ? { q } : {} })
  await router.isReady()
  const w = mount(SearchView, { global: { plugins: [router], stubs: { PhotoViewer: true, AlbumPicker: true } } })
  await flushPromises()
  return { w, router }
}

beforeEach(() => { axios.get.mockReset(); axios.post.mockReset() })

describe('SearchView', () => {
  it('searches the query from the URL and shows what it understood', async () => {
    axios.get.mockResolvedValue(response)
    const { w } = await setup('去年夏天在大理的日落')
    expect(axios.get).toHaveBeenCalledWith('/api/search/smart', { params: { q: '去年夏天在大理的日落', top_k: 200 } })
    expect(w.text()).toContain('2025年夏天')
    expect(w.text()).toContain('大理市')
    expect(w.text()).toContain('画面：日落')
    expect(w.text()).toContain('2 个结果')
    expect(w.text()).toContain('还剩 12')
  })

  it('marks results found by their text and shows the excerpt', async () => {
    axios.get.mockResolvedValue(response)
    const { w } = await setup('发票')
    expect(w.text()).toContain('文字')
    expect(w.text()).toContain('增值税电子普通发票')
  })

  it('removing a chip removes its words from the query', async () => {
    axios.get.mockResolvedValue(response)
    const { w, router } = await setup('去年夏天在大理的日落')
    const placeChip = w.findAll('button[aria-label="去掉 大理市"]')[0]
    await placeChip.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.q).toBe('去年夏天在 的日落'.replace(/\s+/g, ' '))
  })

  it('shows tips instead of searching when the query is empty', async () => {
    const { w } = await setup('')
    expect(axios.get).not.toHaveBeenCalled()
    expect(w.text()).toContain('一个搜索框')
  })

  it('moves selected results to the trash with undo', async () => {
    axios.get.mockResolvedValue(response)
    axios.post.mockResolvedValue({ data: {} })
    const { w } = await setup('日落')
    await w.findAll('button[aria-label="选择"]')[0].trigger('click')
    await w.findAll('button').find(b => b.text() === '移入回收站').trigger('click')
    await flushPromises()
    expect(axios.post).toHaveBeenCalledWith('/api/files/trash', { file_paths: ['/a.jpg'] })
    expect(w.text()).toContain('1 个结果')
  })
})
