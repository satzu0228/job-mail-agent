import { http } from './http'
import type {
  ApplicationEvent,
  AutomationRule,
  AutomationRuleCreate,
  AutomationRuleExecuteResponse,
  EmailAccount,
  EmailAccountCreate,
  EmailConnectionTestResult,
  EmailDetail,
  EmailListItem,
  EmailSyncResult,
  InterviewRound,
  InterviewRoundResultResponse,
  InterviewRoundResultUpdate,
  JobApplication,
  JobApplicationCreate,
  JobApplicationInterviewResultUpdate,
  JobApplicationNextInterviewCreate,
  JobApplicationNextInterviewResponse,
  JobApplicationOfferResultUpdate,
  JobApplicationReopen,
  JobApplicationStageTransition,
  InterviewTaskWithdrawApplication,
  Page,
  ReviewDecisionResponse,
  Reminder,
  ReviewTask,
  Task,
  TaskCreate,
  WorkflowRun,
} from '@/types/api'

async function collectAll<T>(
  fetchPage: (offset: number, limit: number) => Promise<Page<T>>,
  limit = 100,
): Promise<T[]> {
  const items: T[] = []
  let offset = 0
  for (;;) {
    const page = await fetchPage(offset, limit)
    items.push(...page.items)
    offset += page.items.length
    if (page.items.length === 0 || offset >= page.total) return items
  }
}

export const emailAccountApi = {
  list: () => http.get<EmailAccount[]>('/email-accounts').then(({ data }) => data),
  create: (payload: EmailAccountCreate) =>
    http.post<EmailAccount>('/email-accounts', payload).then(({ data }) => data),
  setActive: (id: number, is_active: boolean) =>
    http
      .patch<EmailAccount>(`/email-accounts/${id}/active`, { is_active })
      .then(({ data }) => data),
  setSyncSettings: (id: number, enabled: boolean, interval_minutes: number) =>
    http
      .patch<EmailAccount>(`/email-accounts/${id}/sync-settings`, {
        enabled,
        interval_minutes,
      })
      .then(({ data }) => data),
  test: (id: number) =>
    http
      .post<EmailConnectionTestResult>(`/email-accounts/${id}/test-connection`)
      .then(({ data }) => data),
  sync: (id: number, limit = 50) =>
    http
      .post<EmailSyncResult>(`/email-accounts/${id}/sync`, { limit })
      .then(({ data }) => data),
}

export const emailApi = {
  list: (limit = 100) =>
    collectAll<EmailListItem>((offset, pageLimit) =>
      http
        .get<Page<EmailListItem>>('/emails/query', { params: { offset, limit: pageLimit } })
        .then(({ data }) => data),
    limit),
  query: (params: {
    offset?: number
    limit?: number
    account_id?: number
    keyword?: string
    application_id?: number
    linked?: boolean
    category?: string
  }) => http.get<Page<EmailListItem>>('/emails/query', { params }).then(({ data }) => data),
  detail: (id: number) => http.get<EmailDetail>(`/emails/${id}`).then(({ data }) => data),
  downloadAttachment: (emailId: number, attachmentIndex: number) =>
    http.get<Blob>(`/emails/${emailId}/attachments/${attachmentIndex}`, {
      responseType: 'blob',
    }),
  startWorkflow: (id: number) =>
    http.post<WorkflowRun>(`/emails/${id}/workflow-runs`).then(({ data }) => data),
  proposeArchive: (id: number) =>
    http.post<ReviewTask>(`/emails/${id}/archive-review`).then(({ data }) => data),
  proposeRestore: (id: number) =>
    http.post<ReviewTask>(`/emails/${id}/restore-review`).then(({ data }) => data),
  getWorkflow: (id: string) =>
    http.get<WorkflowRun>(`/workflow-runs/${id}`).then(({ data }) => data),
}

export const applicationApi = {
  list: (limit = 100) =>
    collectAll<JobApplication>((offset, pageLimit) =>
      http
        .get<Page<JobApplication>>('/job-applications/query', { params: { offset, limit: pageLimit } })
        .then(({ data }) => data),
    limit),
  create: (payload: JobApplicationCreate) =>
    http.post<JobApplication>('/job-applications', payload).then(({ data }) => data),
  query: (params: {
    offset?: number
    limit?: number
    keyword?: string
    stage?: string
    status?: string
  }) =>
    http
      .get<Page<JobApplication>>('/job-applications/query', { params })
      .then(({ data }) => data),
  update: (id: number, payload: Partial<JobApplication> & { version: number }) =>
    http.patch<JobApplication>(`/job-applications/${id}`, payload).then(({ data }) => data),
  transitionStage: (id: number, payload: JobApplicationStageTransition) =>
    http
      .post<JobApplication>(`/job-applications/${id}/stage-transitions`, payload)
      .then(({ data }) => data),
  updateInterviewResult: (id: number, payload: JobApplicationInterviewResultUpdate) =>
    http
      .post<JobApplication>(`/job-applications/${id}/interview-result`, payload)
      .then(({ data }) => data),
  scheduleNextInterview: (id: number, payload: JobApplicationNextInterviewCreate) =>
    http
      .post<JobApplicationNextInterviewResponse>(
        `/job-applications/${id}/next-interview`,
        payload,
      )
      .then(({ data }) => data),
  updateOfferResult: (id: number, payload: JobApplicationOfferResultUpdate) =>
    http
      .post<JobApplication>(`/job-applications/${id}/offer-result`, payload)
      .then(({ data }) => data),
  reopen: (id: number, payload: JobApplicationReopen) =>
    http
      .post<JobApplication>(`/job-applications/${id}/reopen`, payload)
      .then(({ data }) => data),
  events: (id: number, offset = 0, limit = 100) =>
    http
      .get<Page<ApplicationEvent>>(`/job-applications/${id}/events`, {
        params: { offset, limit },
      })
      .then(({ data }) => data),
  listInterviewRounds: (id: number) =>
    http
      .get<InterviewRound[]>(`/job-applications/${id}/interview-rounds`)
      .then(({ data }) => data),
  updateInterviewRoundResult: (id: number, payload: InterviewRoundResultUpdate) =>
    http
      .put<InterviewRoundResultResponse>(
        `/job-applications/${id}/interview-rounds/${payload.round_number}/result`,
        payload,
      )
      .then(({ data }) => data),
}

export const taskApi = {
  list: (limit = 100) =>
    collectAll<Task>((offset, pageLimit) =>
      http
        .get<Page<Task>>('/tasks/query', { params: { offset, limit: pageLimit } })
        .then(({ data }) => data),
    limit),
  query: (params: {
    offset?: number
    limit?: number
    application_id?: number
    status?: string
    task_type?: string
    start_from?: string
    start_to?: string
  }) => http.get<Page<Task>>('/tasks/query', { params }).then(({ data }) => data),
  create: (payload: TaskCreate) =>
    http.post<Task>('/tasks', payload).then(({ data }) => data),
  update: (id: number, payload: Partial<Task> & { version: number }) =>
    http.patch<Task>(`/tasks/${id}`, payload).then(({ data }) => data),
  withdrawApplication: (id: number, payload: InterviewTaskWithdrawApplication) =>
    http
      .post<Task>(`/tasks/${id}/withdraw-application`, payload)
      .then(({ data }) => data),
}

export const reminderApi = {
  list: (unreadOnly = false) =>
    http
      .get<Reminder[]>('/reminders', { params: { unread_only: unreadOnly, limit: 100 } })
      .then(({ data }) => data),
  setRead: (id: number, read = true) =>
    http
      .patch<Reminder>(`/reminders/${id}/read`, { read })
      .then(({ data }) => data),
}

export const reviewApi = {
  list: (limit = 100) =>
    collectAll<ReviewTask>((offset, pageLimit) =>
      http
        .get<Page<ReviewTask>>('/review-tasks/query', { params: { offset, limit: pageLimit } })
        .then(({ data }) => data),
    limit),
  query: (params: {
    offset?: number
    limit?: number
    status?: string
    action_type?: string
  }) => http.get<Page<ReviewTask>>('/review-tasks/query', { params }).then(({ data }) => data),
  detail: (id: string) =>
    http.get<ReviewTask>(`/review-tasks/${id}`).then(({ data }) => data),
  decide: (
    id: string,
    payload: {
      version: number
      approve: boolean
      reviewed_payload?: Record<string, unknown> | null
      reason?: string | null
    },
  ) =>
    http
      .post<ReviewDecisionResponse>(`/review-tasks/${id}/decision`, payload)
      .then(({ data }) => data),
}

export const automationRuleApi = {
  list: () => http.get<AutomationRule[]>('/automation-rules').then(({ data }) => data),
  create: (payload: AutomationRuleCreate) =>
    http.post<AutomationRule>('/automation-rules', payload).then(({ data }) => data),
  update: (id: number, payload: Partial<AutomationRule> & { version: number }) =>
    http.patch<AutomationRule>(`/automation-rules/${id}`, payload).then(({ data }) => data),
  preview: (id: number, limit = 20) =>
    http
      .get<{ rule: AutomationRule; candidates: EmailListItem[]; total: number }>(
        `/automation-rules/${id}/preview`,
        { params: { limit } },
      )
      .then(({ data }) => data),
  execute: (id: number) =>
    http
      .post<AutomationRuleExecuteResponse>(`/automation-rules/${id}/execute`)
      .then(({ data }) => data),
}
