import type { EmailAccountCreate } from '@/types/api'

export type MailProviderId = '163' | '126' | 'qq' | 'gmail' | 'custom'

export interface MailProviderPreset {
  id: MailProviderId
  label: string
  emailPlaceholder: string
  imap_host: string
  imap_port: number
  imap_security: EmailAccountCreate['imap_security']
  smtp_host: string
  smtp_port: number
  smtp_security: EmailAccountCreate['smtp_security']
  help?: string
}

export const mailProviderPresets: MailProviderPreset[] = [
  {
    id: '163',
    label: '163 邮箱',
    emailPlaceholder: 'example@163.com',
    imap_host: 'imap.163.com',
    imap_port: 993,
    imap_security: 'SSL',
    smtp_host: 'smtp.163.com',
    smtp_port: 465,
    smtp_security: 'SSL',
  },
  {
    id: '126',
    label: '126 邮箱',
    emailPlaceholder: 'example@126.com',
    imap_host: 'imap.126.com',
    imap_port: 993,
    imap_security: 'SSL',
    smtp_host: 'smtp.126.com',
    smtp_port: 465,
    smtp_security: 'SSL',
  },
  {
    id: 'qq',
    label: 'QQ 邮箱',
    emailPlaceholder: 'example@qq.com',
    imap_host: 'imap.qq.com',
    imap_port: 993,
    imap_security: 'SSL',
    smtp_host: 'smtp.qq.com',
    smtp_port: 465,
    smtp_security: 'SSL',
  },
  {
    id: 'gmail',
    label: 'Gmail',
    emailPlaceholder: 'example@gmail.com',
    imap_host: 'imap.gmail.com',
    imap_port: 993,
    imap_security: 'SSL',
    smtp_host: 'smtp.gmail.com',
    smtp_port: 465,
    smtp_security: 'SSL',
    help: '仅支持应用专用密码，不支持“使用 Google 登录”。账户需先启用两步验证并创建应用专用密码。',
  },
  {
    id: 'custom',
    label: '自定义 IMAP/SMTP',
    emailPlaceholder: 'name@example.com',
    imap_host: '',
    imap_port: 993,
    imap_security: 'SSL',
    smtp_host: '',
    smtp_port: 465,
    smtp_security: 'SSL',
  },
]

export function getMailProviderPreset(provider: string): MailProviderPreset {
  return (
    mailProviderPresets.find((preset) => preset.id === provider) ??
    mailProviderPresets[mailProviderPresets.length - 1]!
  )
}

export function applyMailProviderPreset(
  target: EmailAccountCreate,
  provider: MailProviderId,
): void {
  const preset = getMailProviderPreset(provider)
  target.provider = preset.id
  target.imap_host = preset.imap_host
  target.imap_port = preset.imap_port
  target.imap_security = preset.imap_security
  target.smtp_host = preset.smtp_host
  target.smtp_port = preset.smtp_port
  target.smtp_security = preset.smtp_security
}
