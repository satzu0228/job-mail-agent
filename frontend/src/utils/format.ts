import dayjs from 'dayjs'

export function formatDateTime(value: string | null | undefined): string {
  return value ? dayjs(value).format('YYYY/MM/DD HH:mm') : '—'
}

export function formatDate(value: string | null | undefined): string {
  return value ? dayjs(value).format('YYYY/MM/DD') : '—'
}

export function dateInputValue(value: string | null | undefined): string {
  return value ? dayjs(value).format('YYYY-MM-DD') : ''
}

export function appliedDateTime(value: string | null | undefined): string | null {
  return value ? dayjs(`${value}T00:00:00`).format() : null
}

export function formatRelativeDate(value: string | null | undefined): string {
  if (!value) return '时间未知'
  const target = dayjs(value)
  const today = dayjs()
  if (target.isSame(today, 'day')) return target.format('今天 HH:mm')
  if (target.isSame(today.add(1, 'day'), 'day')) return target.format('明天 HH:mm')
  return target.format('MM月DD日 HH:mm')
}

export function taskTime(task: {
  start_at: string | null
  deadline_at: string | null
}): string | null {
  return task.start_at ?? task.deadline_at
}

export function recipientText(recipient: Record<string, unknown>): string {
  const name = typeof recipient.name === 'string' ? recipient.name : ''
  const address = typeof recipient.address === 'string' ? recipient.address : ''
  return name && address ? `${name} <${address}>` : address || name || '未知地址'
}
