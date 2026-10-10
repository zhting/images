/**
 * Shared viewer behaviour (usePhotoViewer), the album picker, the sidebar
 * status, and Best Shots cleanup — the pieces that replaced per-page copies,
 * window.prompt(), a hard-coded "在线" dot and checkboxes with no action.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))
vi.mock('../composables/useToast', () => ({ toast: vi.fn() }))

import axios from 'axios'
import { toast } from '../composables/useToast'
import { usePhotoViewer } from '../composables/usePhotoViewer'
import AlbumPicker from '../components/AlbumPicker.vue'
import SidebarStatus from '../components/SidebarStatus.vue'
import BestShots from '../views/BestShots.vue'

const lastToastAction = () => toast.mock.calls.at(-1)[1].onAction

beforeEach(() => {
  axios.get.mockReset(); axios.post.mockReset(); toast.mockReset()
  axios.post.mockResolvedValue({ data: {} })
})

describe('usePhotoViewer', () => {
  const photos = () => ref([{ file_path: '/a' }, { file_path: '/b' }, { file_path: '/c' }])

  it('removes immediately, calls the API, and undo puts the photo back in place', async () => {
    const list = photos()
    const onChange = vi.fn()
    const { trashFromViewer } = usePhotoViewer(list, { onChange })
    const b = list.value[1]
    await trashFromViewer(b)
    expect(list.value.map(p => p.file_path)).toEqual(['/a', '/c'])
    expect(axios.post).toHaveBeenCalledWith('/api/files/trash', { file_paths: ['/b'] })
    expect(onChange).toHaveBeenLastCalledWith(-1)

    await lastToastAction()()
    expect(axios.post).toHaveBeenCalledWith('/api/files/restore', { file_paths: ['/b'] })
    expect(list.value.map(p => p.file_path)).toEqual(['/a', '/b', '/c'])
    expect(onChange).toHaveBeenLastCalledWith(+1)
  })

  it('puts the photo back when the request fails', async () => {
    const list = photos()
    axios.post.mockRejectedValueOnce(new Error('500'))
    const { trashFromViewer } = usePhotoViewer(list)
    await trashFromViewer(list.value[0])
    expect(list.value.map(p => p.file_path)).toEqual(['/a', '/b', '/c'])
    expect(toast.mock.calls.at(-1)[1]).toEqual({ type: 'error' })
  })

  it('opens at the clicked index', () => {
    const { viewer, openViewer, closeViewer } = usePhotoViewer(photos())
    openViewer(2)
    expect(viewer).toMatchObject({ open: true, index: 2 })
    closeViewer()
    expect(viewer.open).toBe(false)
  })
})

describe('AlbumPicker', () => {
  it('lists albums and emits the picked one', async () => {
    axios.get.mockResolvedValue({ data: [{ id: 1, name: '旅行', count: 3 }, { id: 2, name: '家人', count: 9 }] })
    const w = mount(AlbumPicker, { props: { modelValue: true, count: 2 } })
    await flushPromises()
    expect(w.text()).toContain('旅行')
    expect(w.text()).toContain('2 张')
    await w.findAll('button').find(b => b.text().includes('家人')).trigger('click')
    expect(w.emitted('pick')[0][0]).toMatchObject({ id: 2, name: '家人' })
    expect(w.emitted('update:modelValue').at(-1)).toEqual([false])
  })

  it('creates a new album and emits it', async () => {
    axios.get.mockResolvedValue({ data: [] })
    axios.post.mockResolvedValue({ data: { id: 7, name: '新相册' } })
    const w = mount(AlbumPicker, { props: { modelValue: true } })
    await flushPromises()
    await w.find('input').setValue('新相册')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(axios.post).toHaveBeenCalledWith('/api/albums', { name: '新相册' })
    expect(w.emitted('pick')[0][0]).toMatchObject({ id: 7 })
  })
})

describe('SidebarStatus', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())
  const stubs = { RouterLink: { template: '<a><slot /></a>' } }
  const show = async (resp) => {
    resp instanceof Error ? axios.get.mockRejectedValue(resp) : axios.get.mockResolvedValue({ data: resp })
    const w = mount(SidebarStatus, { global: { stubs } })
    await vi.advanceTimersByTimeAsync(10); await flushPromises()
    return w
  }
  it('shows indexing progress', async () => {
    expect((await show({ status: 'indexing', current: 37, total: 104 })).text()).toContain('索引中 37 / 104')
  })
  it('shows a disconnected backend', async () => {
    expect((await show(new Error('network'))).text()).toContain('后端未连接')
  })
  it('shows an indexing error', async () => {
    expect((await show({ status: 'error', phase: '扫描失败' })).text()).toContain('上次索引出错')
  })
  it('shows ready otherwise', async () => {
    expect((await show({ status: 'completed' })).text()).toContain('已就绪')
  })
})

describe('BestShots cleanup', () => {
  const groupsResponse = {
    data: {
      has_more: false, next_offset: 0,
      groups: [{
        id: 'g1',
        items: [
          { file_path: '/best.jpg', is_best: true, aesthetic_score: 0.8, captured_time: 1718676901 },
          { file_path: '/x1.jpg', is_best: false, aesthetic_score: 0.5, captured_time: 1718676902 },
          { file_path: '/x2.jpg', is_best: false, aesthetic_score: 0.4, captured_time: 1718676903 },
        ],
      }],
    },
  }

  it('moves the checked photos to the trash and can undo', async () => {
    axios.get.mockResolvedValue(groupsResponse)
    const w = mount(BestShots, { global: { stubs: { PhotoViewer: true } } })
    await flushPromises()

    const cleanAll = w.findAll('button').find(b => b.text().includes('移入回收站'))
    expect(cleanAll.text()).toContain('2')
    await cleanAll.trigger('click')
    await flushPromises()

    expect(axios.post).toHaveBeenCalledWith('/api/files/trash', { file_paths: ['/x1.jpg', '/x2.jpg'] })
    // A burst reduced to one photo is no longer a burst.
    expect(w.text()).toContain('没有发现连拍')

    await lastToastAction()()
    await flushPromises()
    expect(axios.post).toHaveBeenCalledWith('/api/files/restore', { file_paths: ['/x1.jpg', '/x2.jpg'] })
    expect(w.text()).toContain('3 张连拍')
  })

  it('respects unchecked photos', async () => {
    axios.get.mockResolvedValue(JSON.parse(JSON.stringify(groupsResponse)))
    const w = mount(BestShots, { global: { stubs: { PhotoViewer: true } } })
    await flushPromises()
    await w.findAll('input[type=checkbox]')[0].setValue(false)   // keep /x1.jpg
    await w.findAll('button').find(b => b.text().includes('移入回收站')).trigger('click')
    await flushPromises()
    expect(axios.post).toHaveBeenCalledWith('/api/files/trash', { file_paths: ['/x2.jpg'] })
    expect(w.text()).toContain('2 张连拍')
  })
})
