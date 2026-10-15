import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { JobApplication, ReviewDecisionResponse, ReviewTask } from '@/types/api'

const { applicationQuery, decideReview } = vi.hoisted(() => ({
  applicationQuery: vi.fn(),
  decideReview: vi.fn(),
}))

vi.mock('@/api', () => ({
  applicationApi: {
    query: applicationQuery,
  },
  reviewApi: {
    decide: decideReview,
  },
}))

import { useApplicationStore } from './applications'
import { useMailStore } from './mail'
import { useReviewStore } from './reviews'
import { useTaskStore } from './tasks'

const application = {
  id: 8,
  current_stage: 'INTERVIEW',
  status: 'ACTIVE',
  version: 2,
  allowed_transitions: ['OFFER', 'REJECTED', 'WITHDRAWN'],
  allowed_actions: ['UPDATE_DETAILS', 'TRANSITION_STAGE', 'RECORD_INTERVIEW_RESULT'],
} as JobApplication

const review = {
  id: 'review-1',
  source_email_id: 5,
  application_id: 8,
  decision_status: 'APPROVED',
} as ReviewTask

describe('domain stores', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('keeps server pagination metadata and allowed actions unchanged', async () => {
    applicationQuery.mockResolvedValue({
      items: [application],
      total: 61,
      offset: 20,
      limit: 20,
    })
    const store = useApplicationStore()

    await store.loadPage({ offset: 20, limit: 20 })

    expect(store.total).toBe(61)
    expect(store.pageIds).toEqual([8])
    expect(store.applications[0]?.allowed_transitions).toEqual([
      'OFFER',
      'REJECTED',
      'WITHDRAWN',
    ])
  })

  it('invalidates only resources affected by a review decision', async () => {
    decideReview.mockResolvedValue({
      review_task: review,
      execution: null,
      follow_up_review_task: null,
      auto_approved_tasks: [],
    } satisfies ReviewDecisionResponse)
    const store = useReviewStore()

    await store.decide('review-1', { version: 1, approve: true })

    expect(useApplicationStore().invalidatedIds.has(8)).toBe(true)
    expect(useMailStore().invalidatedIds.has(5)).toBe(true)
    expect(useTaskStore().invalidatedApplicationIds.has(8)).toBe(true)
    expect(store.pendingIds).not.toContain('review-1')
  })
})
