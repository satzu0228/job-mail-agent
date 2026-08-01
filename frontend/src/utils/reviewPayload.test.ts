import { describe, expect, it } from 'vitest'

import { visibleReviewPayloadEntries } from './reviewPayload'
import type { ReviewTask } from '@/types/api'

function task(payload: Record<string, unknown>): ReviewTask {
  return {
    id: 'review-send',
    user_id: 1,
    workflow_run_id: 'run-1',
    source_email_id: 26,
    application_id: 4,
    draft_id: 2,
    action_type: 'SEND_REPLY',
    risk_level: 'HIGH',
    proposed_payload: payload,
    reviewed_payload: null,
    status: 'PENDING',
    decision_source: null,
    decision_reason: null,
    reviewed_at: null,
    resource_version: 1,
    version: 1,
    created_at: '2026-07-30T10:00:00Z',
    updated_at: '2026-07-30T10:00:00Z',
  }
}

describe('visibleReviewPayloadEntries', () => {
  it('只展示发送审核需要人工判断的业务字段', () => {
    const entries = visibleReviewPayloadEntries(
      task({
        body: '确认参加面试',
        subject: 'Re: Interview',
        draft_id: 2,
        draft_version: 1,
        schema_version: 'send-reply-review.v1',
        to_recipients: [{ address: 'hr@example.test' }],
        cc_recipients: [],
      }),
    )

    expect(entries.map(([key]) => key)).toEqual([
      'body',
      'subject',
      'to_recipients',
      'cc_recipients',
    ])
  })

  it('阶段审核隐藏数据库主键并展示可读的申请信息', () => {
    const review = task({
      company_name: '远大科技',
      position_name: '前端开发实习生',
      application_id: 105,
      previous_stage: 'APPLIED',
      proposed_stage: 'INTERVIEW',
      validation: { status: 'ALLOWED' },
    })
    review.action_type = 'UPDATE_APPLICATION_STAGE'

    const entries = visibleReviewPayloadEntries(review)

    expect(entries.map(([key]) => key)).toEqual([
      'company_name',
      'position_name',
      'previous_stage',
      'proposed_stage',
      'validation',
    ])
  })
})
