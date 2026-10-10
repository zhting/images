/**
 * Onboarding state machine against the backend's real progress states:
 *   scanning -> scanned -> (POST /index/run) -> indexing -> completed
 * plus error / stopped / empty-folder and re-attaching to a running job.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('axios', () => {
  const get = vi.fn()
  const post = vi.fn()
  return { default: { get, post } }
})
vi.mock('../composables/useToast', () => ({ toast: vi.fn() }))

import axios from 'axios'
import { toast } from '../composables/useToast'
import Onboarding from '../components/Onboarding.vue'

const stubs = { FileBrowserModal: { template: '<div />' } }

/** Serve /index/status from a queue (last value repeats). */
const statusQueue = (...states) => {
  const queue = [...states]
  axios.get.mockImplementation(async (url) => {
    if (url.endsWith('/index/status')) {
      const s = queue.length > 1 ? queue.shift() : queue[0]
      return { data: { current: 0, total: 0, phase: '', ...s } }
    }
    if (url.endsWith('/index/scan')) return { data: { status: 'scan_started' } }
    throw new Error('unexpected GET ' + url)
  })
}

const tick = async (n = 1) => {
  for (let i = 0; i < n; i++) {
    await vi.advanceTimersByTimeAsync(1500)
    await flushPromises()
  }
}

const pickFolder = async (wrapper) => {
  wrapper.findComponent(stubs.FileBrowserModal) // modal is stubbed; call handler directly
  await wrapper.vm.$.setupState.onFolderPicked('/photos')
  await flushPromises()
}

beforeEach(() => {
  vi.useFakeTimers()
  axios.get.mockReset(); axios.post.mockReset(); toast.mockReset()
  axios.post.mockResolvedValue({ data: {} })
})
afterEach(() => vi.useRealTimers())

describe('Onboarding', () => {
  it('runs scan -> index with a request body and only reports success when completed', async () => {
    statusQueue(
      { status: 'idle' },                                   // on mount
      { status: 'scanning' },
      { status: 'scanned', scan_result: { total_ops: 3 } },
      { status: 'indexing', current: 1, total: 3 },
      { status: 'indexing', current: 2, total: 3 },
      { status: 'completed', current: 3, total: 3 },
    )
    const w = mount(Onboarding, { global: { stubs } })
    await flushPromises()
    await pickFolder(w)

    expect(axios.post).toHaveBeenCalledWith('/api/config/paths', { path: '/photos' })
    expect(w.vm.step).toBe('working')

    await tick(2)  // scanning -> scanned
    expect(axios.post).toHaveBeenCalledWith('/api/index/run', { force: false })
    expect(toast).not.toHaveBeenCalled()

    await tick(4)
    expect(toast).toHaveBeenCalledTimes(1)
    expect(toast.mock.calls[0][0]).toContain('索引完成')
    expect(w.emitted('done')).toBeTruthy()
    expect(w.emitted('active').at(-1)).toEqual([false])
  })

  it('shows the failure reason and a retry instead of claiming success', async () => {
    statusQueue({ status: 'idle' }, { status: 'error', phase: "扫描失败: No module named 'x'" })
    const w = mount(Onboarding, { global: { stubs } })
    await flushPromises()
    await pickFolder(w)
    await tick(2)

    expect(w.vm.step).toBe('failed')
    expect(w.text()).toContain("扫描失败: No module named 'x'")
    expect(w.text()).toContain('重试')
    expect(toast).not.toHaveBeenCalled()
    expect(w.emitted('active').at(-1)).toEqual([true])  // card stays visible
  })

  it('reports an empty folder instead of starting an empty run', async () => {
    statusQueue({ status: 'idle' }, { status: 'scanned', scan_result: { total_ops: 0 } })
    const w = mount(Onboarding, { global: { stubs } })
    await flushPromises()
    await pickFolder(w)
    await tick(2)

    expect(w.vm.step).toBe('empty')
    expect(axios.post).not.toHaveBeenCalledWith('/api/index/run', expect.anything())
  })

  it('fails visibly when the run cannot be started', async () => {
    statusQueue({ status: 'idle' }, { status: 'scanned', scan_result: { total_ops: 5 } })
    axios.post.mockImplementation(async (url) => {
      if (url.endsWith('/index/run')) {
        const err = new Error('422'); err.response = { status: 422, data: { detail: 'Field required' } }
        throw err
      }
      return { data: {} }
    })
    const w = mount(Onboarding, { global: { stubs } })
    await flushPromises()
    await pickFolder(w)
    await tick(2)

    expect(w.vm.step).toBe('failed')
    expect(w.text()).toContain('Field required')
    expect(toast).not.toHaveBeenCalled()
  })

  it('treats a stopped run as resumable', async () => {
    statusQueue({ status: 'idle' }, { status: 'stopped' })
    const w = mount(Onboarding, { global: { stubs } })
    await flushPromises()
    await pickFolder(w)
    await tick(2)
    expect(w.vm.step).toBe('failed')
    expect(w.text()).toContain('继续索引')
  })

  it('re-attaches to a run already in progress when mounted', async () => {
    statusQueue(
      { status: 'indexing', current: 10, total: 40 },   // on mount
      { status: 'indexing', current: 10, total: 40 },   // first poll
      { status: 'completed', current: 40, total: 40 },
    )
    const w = mount(Onboarding, { global: { stubs } })
    await vi.advanceTimersByTimeAsync(10)   // let onMounted's status request resolve
    await flushPromises()
    expect(w.vm.step).toBe('working')
    expect(w.text()).toContain('10 / 40')
    await tick(2)
    expect(w.emitted('done')).toBeTruthy()
  })
})
