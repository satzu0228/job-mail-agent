import { describe, expect, it } from 'vitest'

import { applyMailProviderPreset, getMailProviderPreset } from './mailProviders'
import type { EmailAccountCreate } from '@/types/api'

function form(): EmailAccountCreate {
  return {
    provider: '163',
    email_address: '',
    imap_host: 'old.example.com',
    imap_port: 143,
    imap_security: 'STARTTLS',
    smtp_host: 'old.example.com',
    smtp_port: 587,
    smtp_security: 'STARTTLS',
    credential_ref: 'JOB_MAIL_EMAIL_AUTH_CODE',
    is_active: true,
  }
}

describe('邮箱 Provider 预设', () => {
  it.each([
    ['163', 'imap.163.com', 'smtp.163.com'],
    ['126', 'imap.126.com', 'smtp.126.com'],
    ['qq', 'imap.qq.com', 'smtp.qq.com'],
    ['gmail', 'imap.gmail.com', 'smtp.gmail.com'],
  ] as const)('映射 %s 的服务器配置', (provider, imap, smtp) => {
    const target = form()
    applyMailProviderPreset(target, provider)
    expect(target.imap_host).toBe(imap)
    expect(target.smtp_host).toBe(smtp)
    expect(target.imap_port).toBe(993)
    expect(target.smtp_port).toBe(465)
  })

  it('切换到自定义时不会遗留上一个预设的主机', () => {
    const target = form()
    applyMailProviderPreset(target, 'gmail')
    applyMailProviderPreset(target, 'custom')
    expect(target.imap_host).toBe('')
    expect(target.smtp_host).toBe('')
  })

  it('未知 Provider 按自定义配置处理', () => {
    expect(getMailProviderPreset('unknown').id).toBe('custom')
  })
})
