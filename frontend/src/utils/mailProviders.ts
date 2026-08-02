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
  authorizationTitle: string
  authorizationSteps: string[]
  authorizationUrl?: string
  authorizationLinkLabel?: string
  authorizationHint: string
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
    authorizationTitle: '获取 163 邮箱授权码',
    authorizationSteps: [
      '登录网页版 163 邮箱，进入“设置 > POP3/SMTP/IMAP”。',
      '开启 IMAP/SMTP 服务，按页面提示完成短信验证。',
      '复制生成的授权码。授权码只显示一次，不是邮箱登录密码。',
    ],
    authorizationUrl: 'https://mail.163.com/',
    authorizationLinkLabel: '打开 163 邮箱',
    authorizationHint: '请填写开启 IMAP/SMTP 后生成的授权码，不要填写邮箱登录密码。',
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
    authorizationTitle: '获取 126 邮箱授权码',
    authorizationSteps: [
      '登录网页版 126 邮箱，进入“设置 > POP3/SMTP/IMAP”。',
      '开启 IMAP/SMTP 服务，按页面提示完成安全验证。',
      '复制新生成的授权码。',
    ],
    authorizationUrl: 'https://mail.126.com/',
    authorizationLinkLabel: '打开 126 邮箱',
    authorizationHint: '请填写邮箱服务生成的授权码，不要填写邮箱登录密码。',
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
    authorizationTitle: '获取 QQ 邮箱授权码',
    authorizationSteps: [
      '登录网页版 QQ 邮箱，进入“设置 > 账号与安全”。',
      '在“安全设置”中找到 IMAP/SMTP 服务并开启。',
      '按提示验证身份，复制生成的授权码。',
    ],
    authorizationUrl: 'https://mail.qq.com/',
    authorizationLinkLabel: '打开 QQ 邮箱',
    authorizationHint: 'QQ 邮箱需使用单独生成的授权码，不能使用 QQ 密码。',
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
    authorizationTitle: '创建 Google 应用专用密码',
    authorizationSteps: [
      '打开 Google 账号安全设置，先启用“两步验证”。',
      '进入“应用专用密码”，为邮件应用创建一个新密码。',
      '复制显示的 16 位应用专用密码并填入下方。',
    ],
    authorizationUrl: 'https://myaccount.google.com/apppasswords',
    authorizationLinkLabel: '打开应用专用密码',
    authorizationHint: '仅支持应用专用密码，暂不支持“使用 Google 登录”。',
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
    authorizationTitle: '获取邮箱授权码',
    authorizationSteps: [
      '在邮箱服务商的安全设置中开启 IMAP 和 SMTP。',
      '创建用于第三方邮件客户端的授权码或应用专用密码。',
      '确认服务器地址与端口后，将授权码填入下方。',
    ],
    authorizationHint: '不同服务商名称可能是“授权码”“客户端专用密码”或“应用专用密码”。',
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
