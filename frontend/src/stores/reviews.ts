import { defineStore } from 'pinia'

import { reviewApi } from '@/api'
import { useApplicationStore } from '@/stores/applications'
import { useMailStore } from '@/stores/mail'
import { useTaskStore } from '@/stores/tasks'
import type { ReviewDecisionResponse, ReviewTask } from '@/types/api'

export const useReviewStore = defineStore('reviews', {
  state: () => ({
    reviewsById: {} as Record<string, ReviewTask>,
    pendingIds: [] as string[],
    pageIds: [] as string[],
    total: 0,
    loading: false,
  }),
  getters: {
    reviews: (state) => state.pageIds.flatMap((id) => state.reviewsById[id] ?? []),
    pendingCount: (state) => state.pendingIds.length,
  },
  actions: {
    upsert(task: ReviewTask) {
      this.reviewsById[task.id] = task
      if (!this.pageIds.includes(task.id)) this.pageIds.unshift(task.id)
      const pending = task.decision_status === 'PENDING'
      if (pending && !this.pendingIds.includes(task.id)) this.pendingIds.unshift(task.id)
      if (!pending) this.pendingIds = this.pendingIds.filter((id) => id !== task.id)
    },
    async loadPage(params: Parameters<typeof reviewApi.query>[0] = {}) {
      this.loading = true
      try {
        const page = await reviewApi.query({ offset: 0, limit: 100, ...params })
        for (const review of page.items) this.upsert(review)
        this.pageIds = page.items.map((item) => item.id)
        this.total = page.total
        return page
      } finally {
        this.loading = false
      }
    },
    async loadPending() {
      return this.loadPage({ status: 'PENDING', offset: 0, limit: 100 })
    },
    async detail(id: string) {
      const task = await reviewApi.detail(id)
      this.upsert(task)
      return task
    },
    async decide(
      id: string,
      payload: Parameters<typeof reviewApi.decide>[1],
    ): Promise<ReviewDecisionResponse> {
      const response = await reviewApi.decide(id, payload)
      this.upsert(response.review_task)
      if (response.follow_up_review_task) this.upsert(response.follow_up_review_task)
      for (const task of response.auto_approved_tasks ?? []) this.upsert(task)

      const task = response.review_task
      useApplicationStore().invalidate(task.application_id)
      useMailStore().invalidate(task.source_email_id)
      useTaskStore().invalidateApplication(task.application_id)
      return response
    },
  },
})
