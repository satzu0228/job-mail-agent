import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { usePollingStore } from './polling'

describe('polling store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    vi.stubGlobal('document', {
      hidden: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })
    vi.stubGlobal('window', {
      setTimeout: globalThis.setTimeout,
      clearTimeout: globalThis.clearTimeout,
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('prevents overlapping polls', async () => {
    let resolve!: () => void
    const pending = new Promise<void>((done) => { resolve = done })
    const subscriber = vi.fn(() => pending)
    const store = usePollingStore()
    const unsubscribe = store.subscribe('test', subscriber)

    const first = store.refreshNow()
    const second = store.refreshNow()
    expect(subscriber).toHaveBeenCalledTimes(1)
    resolve()
    await Promise.all([first, second])
    expect(store.lastSuccessAt).not.toBeNull()
    unsubscribe()
  })

  it('does not poll while the page is hidden', async () => {
    Object.defineProperty(document, 'hidden', { configurable: true, value: true })
    const subscriber = vi.fn()
    const store = usePollingStore()
    const unsubscribe = store.subscribe('hidden', subscriber)

    await store.refreshNow()
    await vi.advanceTimersByTimeAsync(60_000)

    expect(subscriber).not.toHaveBeenCalled()
    unsubscribe()
  })
})
