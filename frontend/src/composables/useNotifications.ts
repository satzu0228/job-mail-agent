import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { formatRelativeDate } from '@/utils/format'
import { reviewActionMeta } from '@/utils/dictionaries'
import type { Reminder, ReviewTask } from '@/types/api'

const SEEN_CAP = 200

export function useNotifications() {
  const router = useRouter()

  const isSupported = ref(typeof Notification !== 'undefined')
  const permission = ref<NotificationPermission>(
    isSupported.value ? Notification.permission : 'denied',
  )
  const seenReminderIds = ref<Set<number>>(new Set())
  const seenReviewTaskIds = ref<Set<string>>(new Set())

  async function requestPermission(): Promise<void> {
    if (!isSupported.value) return
    try {
      const result = await Notification.requestPermission()
      permission.value = result
    } catch {
      // 用户取消或浏览器拒绝，保持当前状态。
    }
  }

  function notifyNewReminders(items: Reminder[]): void {
    if (!isSupported.value || permission.value !== 'granted') return
    for (const item of items) {
      if (seenReminderIds.value.has(item.id)) continue
      _track(seenReminderIds.value, item.id)
      notify(`📅 ${item.title}`, {
        body: `时间：${formatRelativeDate(item.event_at)}`,
        tag: `reminder-${item.id}`,
        onClick() {
          window.focus()
          void router.push('/calendar')
        },
      })
    }
  }

  function notifyNewReviews(items: ReviewTask[]): void {
    if (!isSupported.value || permission.value !== 'granted') return
    for (const item of items) {
      if (seenReviewTaskIds.value.has(item.id)) continue
      _track(seenReviewTaskIds.value, item.id)
      const label = reviewActionMeta[item.action_type] ?? item.action_type
      notify(`✅ 待审核：${label}`, {
        body: item.risk_level === 'HIGH' ? '高风险操作，请尽快处理' : '有新的审核等待你处理',
        tag: `review-${item.id}`,
        onClick() {
          window.focus()
          void router.push(`/reviews/${item.id}`)
        },
      })
    }
  }

  function notify(
    title: string,
    options: { body: string; tag: string; onClick: () => void },
  ): void {
    if (!isSupported.value || permission.value !== 'granted') return
    try {
      const notification = new Notification(title, {
        body: options.body,
        tag: options.tag,
        icon: '/favicon.ico',
        requireInteraction: false,
      })
      notification.onclick = () => {
        notification.close()
        options.onClick()
      }
    } catch {
      // 浏览器拒绝或 API 不可用，静默跳过。
    }
  }

  // ------------------------------------------------------------------
  // 内部
  // ------------------------------------------------------------------

  function _track(set: Set<number> | Set<string>, id: number | string): void {
    if (set.size >= SEEN_CAP) {
      set.clear()
    }
    set.add(id as never)
  }

  return {
    isSupported,
    permission,
    seenReminderIds,
    seenReviewTaskIds,
    requestPermission,
    notifyNewReminders,
    notifyNewReviews,
  }
}
