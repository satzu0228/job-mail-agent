import type {
  ApplicationStage,
  EmailCategory,
  EmailPriority,
  ReviewActionType,
  ReviewTaskStatus,
  RiskLevel,
  TaskStatus,
  TaskType,
} from '@/types/api'

type TagKind = 'primary' | 'success' | 'warning' | 'danger' | 'info'

export const stageMeta: Record<ApplicationStage, { label: string; type: TagKind }> = {
  APPLIED: { label: '已投递', type: 'info' },
  ASSESSMENT: { label: '笔试', type: 'warning' },
  INTERVIEW: { label: '面试', type: 'primary' },
  OFFER: { label: '录用', type: 'success' },
  REJECTED: { label: '已拒绝', type: 'danger' },
  WITHDRAWN: { label: '已撤回', type: 'info' },
}

export const categoryMeta: Record<EmailCategory, { label: string; type: TagKind }> = {
  INTERVIEW: { label: '面试邀请', type: 'primary' },
  ASSESSMENT: { label: '笔试测评', type: 'warning' },
  OFFER: { label: '录用通知', type: 'success' },
  REJECTION: { label: '拒信', type: 'danger' },
  MATERIAL_REQUEST: { label: '材料补充', type: 'warning' },
  APPLICATION_UPDATE: { label: '申请进展', type: 'primary' },
  RECRUITER_COMMUNICATION: { label: '招聘沟通', type: 'info' },
  JOB_RELATED_OTHER: { label: '其他求职', type: 'info' },
  NON_JOB: { label: '非求职', type: 'info' },
}

export const priorityMeta: Record<EmailPriority, { label: string; type: TagKind }> = {
  LOW: { label: '低', type: 'info' },
  MEDIUM: { label: '普通', type: 'info' },
  HIGH: { label: '重要', type: 'warning' },
  URGENT: { label: '紧急', type: 'danger' },
}

export const reviewActionMeta: Record<ReviewActionType, string> = {
  CREATE_APPLICATION: '新建申请',
  LINK_APPLICATION: '关联申请',
  UPDATE_APPLICATION_STAGE: '更新阶段',
  CREATE_TASK: '创建日程',
  UPDATE_TASK: '更新日程',
  SEND_REPLY: '发送回复',
  ARCHIVE_EMAIL: '归档邮件',
  RESTORE_EMAIL: '恢复邮件',
}

export const reviewStatusMeta: Record<ReviewTaskStatus, { label: string; type: TagKind }> = {
  PENDING: { label: '待审核', type: 'warning' },
  APPROVED: { label: '已批准', type: 'primary' },
  REJECTED: { label: '已拒绝', type: 'danger' },
  CANCELLED: { label: '已取消', type: 'info' },
  EXPIRED: { label: '已过期', type: 'info' },
  EXECUTING: { label: '执行中', type: 'warning' },
  SUCCEEDED: { label: '已完成', type: 'success' },
  FAILED: { label: '执行失败', type: 'danger' },
  UNKNOWN: { label: '状态未知', type: 'info' },
}

export const riskMeta: Record<RiskLevel, { label: string; type: TagKind }> = {
  LOW: { label: '低风险', type: 'info' },
  MEDIUM: { label: '中风险', type: 'warning' },
  HIGH: { label: '高风险', type: 'danger' },
}

export const taskTypeMeta: Record<TaskType, { label: string; color: string }> = {
  INTERVIEW: { label: '面试', color: '#3370ff' },
  ASSESSMENT: { label: '笔试', color: '#7b61d1' },
  MATERIAL: { label: '材料', color: '#d27b17' },
  DEADLINE: { label: '截止', color: '#d54941' },
  OTHER: { label: '其他', color: '#8f959e' },
}

export const taskStatusMeta: Record<TaskStatus, { label: string; type: TagKind }> = {
  PENDING: { label: '待确认', type: 'warning' },
  CONFIRMED: { label: '已确认', type: 'primary' },
  COMPLETED: { label: '已完成', type: 'success' },
  CANCELLED: { label: '已取消', type: 'info' },
}

export const eventTypeLabels: Record<string, string> = {
  APPLICATION_CREATED: '创建申请',
  EMAIL_LINKED: '关联邮件',
  STAGE_CHANGED: '阶段变更',
  EMAIL_EVENT: '邮件事件',
  INTERVIEW: '面试安排',
  ASSESSMENT: '笔试测评',
  OFFER: '录用通知',
  REJECTION: '流程终止',
  MATERIAL_REQUEST: '材料补充',
  APPLICATION_UPDATE: '申请进展',
  RECRUITER_COMMUNICATION: '招聘沟通',
  JOB_RELATED_OTHER: '其他求职事件',
}

export const syncStatusLabels: Record<string, string> = {
  SUCCEEDED: '同步成功',
  PARTIAL: '部分成功',
  FAILED: '同步失败',
}

export const analysisFieldLabels: Record<string, string> = {
  COMPANY: '公司',
  POSITION: '岗位',
  PROPOSED_STAGE: '求职阶段',
  EVENT_TYPE: '事件类型',
  CONTACT_NAME: '联系人',
  CONTACT_EMAIL: '联系邮箱',
  EVENT_TIME: '事件时间',
  DEADLINE: '截止时间',
  LOCATION: '地点',
  MEETING_URL: '会议链接',
  MATERIALS: '所需材料',
}

export function analysisFieldLabel(value: string): string {
  return analysisFieldLabels[value.toUpperCase()] ?? `未识别字段：${value}`
}

export const workflowStatusLabels: Record<string, string> = {
  PENDING: '等待处理',
  RUNNING: '处理中',
  WAITING_REVIEW: '等待人工审核',
  SUCCEEDED: '处理完成',
  FAILED: '处理失败',
  CANCELLED: '已取消',
}

export function enumValueLabel(value: string): string {
  const labels: Record<string, string> = {
    APPLIED: '已投递',
    ASSESSMENT: '笔试',
    INTERVIEW: '面试',
    OFFER: '录用',
    REJECTED: '已拒绝',
    WITHDRAWN: '已撤回',
    PENDING: '待处理',
    CONFIRMED: '已确认',
    COMPLETED: '已完成',
    CANCELLED: '已取消',
    APPROVED: '已批准',
    SUCCEEDED: '已完成',
    FAILED: '失败',
    ALLOWED: '允许',
    DENIED: '不允许',
    USER: '用户确认',
    RULE: '规则确认',
  }
  return labels[value] ?? value
}
