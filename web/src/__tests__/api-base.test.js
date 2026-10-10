import { describe, it, expect } from 'vitest'
import { API_BASE } from '../api/base'

describe('API_BASE', () => {
  // Same-origin /api works for dev (Vite proxy), the packaged app (backend
  // serves the page) and phones on the LAN alike; an absolute localhost URL
  // only ever worked for the first.
  it('is same-origin /api', () => {
    expect(API_BASE).toBe('/api')
  })
})
