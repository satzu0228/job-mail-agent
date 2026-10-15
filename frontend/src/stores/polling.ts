import { defineStore } from 'pinia'
import { ref } from 'vue'

type PollSubscriber = () => void | Promise<void>

export const usePollingStore = defineStore('polling', () => {
  const inFlight = ref(false)
  const lastSuccessAt = ref<string | null>(null)
  const backoffMs = ref(5_000)
  const subscribers = new Map<string, PollSubscriber>()
  let timer: number | undefined
  let listening = false

  async function tick() {
    if (inFlight.value || document.hidden) return
    inFlight.value = true
    try {
      await Promise.all([...subscribers.values()].map((subscriber) => subscriber()))
      lastSuccessAt.value = new Date().toISOString()
      backoffMs.value = 5_000
    } catch {
      backoffMs.value = Math.min(backoffMs.value * 2, 60_000)
    } finally {
      inFlight.value = false
      schedule()
    }
  }

  function schedule() {
    if (timer) window.clearTimeout(timer)
    if (!document.hidden && subscribers.size > 0) {
      timer = window.setTimeout(() => void tick(), backoffMs.value)
    }
  }

  function onVisibilityChange() {
    if (document.hidden && timer) window.clearTimeout(timer)
    else void tick()
  }

  function subscribe(key: string, subscriber: PollSubscriber) {
    subscribers.set(key, subscriber)
    if (!listening) {
      document.addEventListener('visibilitychange', onVisibilityChange)
      listening = true
    }
    schedule()
    return () => {
      subscribers.delete(key)
      schedule()
      if (subscribers.size === 0 && listening) {
        document.removeEventListener('visibilitychange', onVisibilityChange)
        listening = false
      }
    }
  }

  function refreshNow() {
    return tick()
  }

  return { inFlight, lastSuccessAt, backoffMs, subscribe, refreshNow }
})
