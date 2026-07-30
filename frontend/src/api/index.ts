import { http } from './http'
import type {
  ApplicationEvent,
  EmailAccount,
  EmailAccountCreate,
  EmailConnectionTestResult,
  EmailDetail,
  EmailListItem,
  EmailSyncResult,
  JobApplication,
  JobApplicationCreate,
  Page,
  ReviewDecisionResponse,
  ReviewTask,
  Task,
  WorkflowRun,
} from '@/types/api'

export const emailAccountApi = {
  list: () => http.get<EmailAccount[]>('/email-accounts').then(({ data }) => data),
  create: (payload: EmailAccountCreate) =>
    http.post<EmailAccount>('/email-accounts', payload).then(({ data }) => data),
  setActive: (id: number, is_active: boolean) =>
    http
      .patch<EmailAccount>(`/email-accounts/${id}/active`, { is_active })
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
    http.get<EmailListItem[]>('/emails', { params: { limit } }).then(({ data }) => data),
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
  getWorkflow: (id: string) =>
    http.get<WorkflowRun>(`/workflow-runs/${id}`).then(({ data }) => data),
}

export const applicationApi = {
  list: (limit = 100) =>
    http
      .get<JobApplication[]>('/job-applications', { params: { limit } })
      .then(({ data }) => data),
  create: (payload: JobApplicationCreate) =>
    http.post<JobApplication>('/job-applications', payload).then(({ data }) => data),
  update: (id: number, payload: Partial<JobApplication> & { version: number }) =>
    http.patch<JobApplication>(`/job-applications/${id}`, payload).then(({ data }) => data),
  events: (id: number, offset = 0, limit = 100) =>
    http
      .get<Page<ApplicationEvent>>(`/job-applications/${id}/events`, {
        params: { offset, limit },
      })
      .then(({ data }) => data),
}

export const taskApi = {
  list: (limit = 100) =>
    http.get<Task[]>('/tasks', { params: { limit } }).then(({ data }) => data),
  update: (id: number, payload: Partial<Task> & { version: number }) =>
    http.patch<Task>(`/tasks/${id}`, payload).then(({ data }) => data),
}

export const reviewApi = {
  list: (limit = 100) =>
    http.get<ReviewTask[]>('/review-tasks', { params: { limit } }).then(({ data }) => data),
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
