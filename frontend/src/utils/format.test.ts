import { describe, expect, it } from 'vitest'

import {
  appliedDateTime,
  dateInputValue,
  formatDate,
  recipientText,
  taskTime,
} from './format'

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

  it('keeps application input at date precision', () => {
    expect(dateInputValue('2026-07-16T00:00:00+08:00')).toBe('2026-07-16')
  })

  it('converts an application date to an aware midnight for the API', () => {
    expect(appliedDateTime('2026-07-16')).toMatch(/^2026-07-16T00:00:00[+-]\d{2}:\d{2}$/)
  })
})
