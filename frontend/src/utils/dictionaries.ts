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
  OFFER: { label: 'Offer', type: 'success' },
  REJECTED: { label: '已拒绝', type: 'danger' },
  WITHDRAWN: { label: '已撤回', type: 'info' },
}

export const categoryMeta: Record<EmailCategory, { label: string; type: TagKind }> = {
  INTERVIEW: { label: '面试邀请', type: 'primary' },
  ASSESSMENT: { label: '笔试测评', type: 'warning' },
  OFFER: { label: 'Offer', type: 'success' },
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
