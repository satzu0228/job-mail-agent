import { describe, expect, it } from 'vitest'

import { formatDate, recipientText, taskTime } from './format'

describe('format utilities', () => {
  it('formats missing dates consistently', () => {
    expect(formatDate(null)).toBe('—')
  })

  it('uses task start time before deadline', () => {
    expect(taskTime({ start_at: '2026-07-30T01:00:00Z', deadline_at: 'later' })).toBe(
      '2026-07-30T01:00:00Z',
    )
  })

  it('renders recipient name and address', () => {
    expect(recipientText({ name: '招聘 HR', address: 'hr@example.com' })).toBe(
      '招聘 HR <hr@example.com>',
    )
  })
})
