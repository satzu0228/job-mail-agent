export type TransportSecurity = 'SSL' | 'STARTTLS'
export type ApplicationStage =
  | 'APPLIED'
  | 'ASSESSMENT'
  | 'INTERVIEW'
  | 'OFFER'
  | 'REJECTED'
  | 'WITHDRAWN'
export type ApplicationStatus = 'ACTIVE' | 'CLOSED' | 'WITHDRAWN'
export type InterviewResult = 'PENDING' | 'PASSED' | 'FAILED'
export type OfferResult = 'PENDING' | 'ACCEPTED' | 'DECLINED'
export type ApplicationSource = 'MANUAL' | 'EMAIL'
export type EmailCategory =
  | 'INTERVIEW'
  | 'ASSESSMENT'
  | 'OFFER'
  | 'REJECTION'
  | 'MATERIAL_REQUEST'
  | 'APPLICATION_UPDATE'
  | 'RECRUITER_COMMUNICATION'
  | 'JOB_RELATED_OTHER'
  | 'NON_JOB'
export type EmailPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT'
export type ReviewTaskStatus =
  | 'PENDING'
  | 'APPROVED'
  | 'REJECTED'
  | 'CANCELLED'
  | 'EXPIRED'
  | 'EXECUTING'
  | 'SUCCEEDED'
  | 'FAILED'
  | 'UNKNOWN'
export type ReviewActionType =
  | 'CREATE_APPLICATION'
  | 'LINK_APPLICATION'
  | 'UPDATE_APPLICATION_STAGE'
  | 'CREATE_TASK'
  | 'UPDATE_TASK'
  | 'SEND_REPLY'
  | 'ARCHIVE_EMAIL'
  | 'RESTORE_EMAIL'
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH'
export type TaskType = 'INTERVIEW' | 'ASSESSMENT' | 'MATERIAL' | 'DEADLINE' | 'OTHER'
export type TaskStatus = 'PENDING' | 'CONFIRMED' | 'COMPLETED' | 'CANCELLED'
export type WorkflowRunStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'WAITING_REVIEW'
  | 'SUCCEEDED'
  | 'FAILED'
  | 'CANCELLED'

export interface EmailAccount {
  id: number
  provider: string
  email_address: string
  email_address_masked: string
  imap_host: string
  imap_port: number
  imap_security: TransportSecurity
  smtp_host: string
  smtp_port: number
  smtp_security: TransportSecurity
  is_active: boolean
  auto_sync_enabled: boolean
  sync_interval_minutes: number
  next_sync_at: string | null
  last_auto_sync_at: string | null
  inbox_uid_validity: number | null
  last_synced_uid: number | null
  last_sync_at: string | null
  last_sync_status: string | null
  last_sync_error: string | null
  created_at: string
  updated_at: string
}

export interface EmailAccountCreate {
  provider: string
  email_address: string
  imap_host: string
  imap_port: number
  imap_security: TransportSecurity
  smtp_host: string
  smtp_port: number
  smtp_security: TransportSecurity
  credential_ref: string
  is_active: boolean
}

export interface EmailConnectionTestResult {
  imap: { success: boolean; message: string }
  smtp: { success: boolean; message: string }
}

export interface EmailSyncResult {
  account_id: number
  folder: string
  uid_validity: number
  examined: number
  created: number
  skipped: number
  failed: number
  created_email_ids: number[]
}

export interface EmailListItem {
  id: number
  account_id: number
  application_id: number | null
  subject: string
  from_name: string | null
  from_address: string
  to_recipients: Array<Record<string, unknown>>
  direction: 'RECEIVED' | 'SENT'
  received_at: string | null
  parse_status: 'PENDING' | 'SUCCEEDED' | 'PARTIAL' | 'FAILED'
  archive_status: 'NONE' | 'PROPOSED' | 'ARCHIVED' | 'RESTORED' | 'FAILED'
}

export interface EmailAnalysis {
  id: number
  email_id: number
  version: number
  is_current: boolean
  status: 'VALID' | 'PENDING_CONFIRMATION' | 'INVALID'
  is_job_related: boolean
  category: EmailCategory
  priority: EmailPriority
  should_reply: boolean
  classification_confidence: number
  extraction_confidence: number | null
  summary: string | null
  company_name: string | null
  position_name: string | null
  event_type: string | null
  event_time: string | null
  deadline_at: string | null
  source_timezone: string | null
  extraction_json: Record<string, unknown>
  evidence_json: Record<string, unknown>
  missing_fields: string[]
  schema_version: string
  created_at: string
}

export interface EmailDetail extends EmailListItem {
  message_id: string | null
  to_recipients: Array<Record<string, unknown>>
  cc_recipients: Array<Record<string, unknown>>
  sent_at: string | null
  plain_body: string | null
  html_sanitized: string | null
  attachment_metadata: Array<Record<string, unknown>>
  current_analysis: EmailAnalysis | null
}

export interface JobApplication {
  id: number
  user_id: number
  company_name: string
  company_alias: string | null
  position_name: string
  location: string | null
  current_stage: ApplicationStage
  interview_result: InterviewResult | null
  offer_result: OfferResult | null
  status: ApplicationStatus
  source: ApplicationSource
  applied_at: string | null
  contact_name: string | null
  contact_email: string | null
  notes: string | null
  version: number
  created_at: string
  updated_at: string
}

export interface JobApplicationCreate {
  company_name: string
  company_alias?: string | null
  position_name: string
  location?: string | null
  applied_at?: string | null
  contact_name?: string | null
  contact_email?: string | null
  notes?: string | null
}

export interface JobApplicationStageTransition {
  version: number
  proposed_stage: ApplicationStage
  reason: string
}

export interface JobApplicationInterviewResultUpdate {
  version: number
  result: InterviewResult
  reason: string
}

export interface JobApplicationNextInterviewCreate {
  version: number
  title: string
  description?: string | null
  raw_time_text?: string | null
  start_at: string
  deadline_at?: string | null
  source_timezone?: string | null
  location?: string | null
  meeting_url?: string | null
  reason: string
}

export interface JobApplicationNextInterviewResponse {
  application: JobApplication
  task: Task
}

export interface JobApplicationOfferResultUpdate {
  version: number
  result: OfferResult
  reason: string
}

export interface JobApplicationReopen {
  version: number
  target_stage: Exclude<ApplicationStage, 'REJECTED' | 'WITHDRAWN'>
  reason: string
}

export interface ApplicationEvent {
  id: number
  application_id: number
  source_email_id: number | null
  workflow_run_id: string | null
  event_type: string
  previous_stage: ApplicationStage | null
  proposed_stage: ApplicationStage | null
  confirmed_stage: ApplicationStage | null
  raw_time_text: string | null
  event_at: string | null
  source_timezone: string | null
  details: Record<string, unknown> | null
  created_at: string
}

export interface Page<T> {
  items: T[]
  total: number
  offset: number
  limit: number
}

export interface Task {
  id: number
  user_id: number
  application_id: number | null
  source_email_id: number | null
  task_type: TaskType
  interview_round: number | null
  title: string
  description: string | null
  raw_time_text: string | null
  start_at: string | null
  deadline_at: string | null
  source_timezone: string | null
  location: string | null
  meeting_url: string | null
  status: TaskStatus
  version: number
  created_at: string
  updated_at: string
}

export interface TaskCreate {
  application_id?: number | null
  source_email_id?: number | null
  task_type: TaskType
  interview_round?: number | null
  title: string
  description?: string | null
  raw_time_text?: string | null
  start_at?: string | null
  deadline_at?: string | null
  source_timezone?: string | null
  location?: string | null
  meeting_url?: string | null
  status?: TaskStatus
}

export interface AutomationRule {
  id: number
  user_id: number
  account_id: number | null
  name: string
  rule_type: 'LOW_PRIORITY_ARCHIVE'
  conditions: Record<string, unknown>
  action_config: Record<string, unknown>
  requires_confirmation: boolean
  is_enabled: boolean
  version: number
  created_at: string
  updated_at: string
}

export interface AutomationRuleCreate {
  account_id?: number | null
  name: string
  rule_type?: 'LOW_PRIORITY_ARCHIVE'
  conditions?: Record<string, unknown>
  action_config?: Record<string, unknown>
  requires_confirmation?: boolean
  is_enabled?: boolean
}

export interface AutomationRuleExecuteResponse {
  created_review_task_ids: string[]
  skipped_email_ids: number[]
  failed_email_ids: Record<number, string>
}

export interface InterviewTaskWithdrawApplication {
  version: number
  application_version: number
  reason: string
}

export interface Reminder {
  id: number
  user_id: number
  task_id: number
  title: string
  remind_at: string
  event_at: string
  status: 'DELIVERED' | 'READ' | 'CANCELLED'
  delivered_at: string
  read_at: string | null
  created_at: string
  updated_at: string
}

export interface ReviewTask {
  id: string
  user_id: number
  workflow_run_id: string
  source_email_id: number | null
  application_id: number | null
  draft_id: number | null
  action_type: ReviewActionType
  risk_level: RiskLevel
  proposed_payload: Record<string, unknown>
  reviewed_payload: Record<string, unknown> | null
  status: ReviewTaskStatus
  decision_source: 'USER' | 'RULE' | null
  decision_reason: string | null
  reviewed_at: string | null
  resource_version: number
  version: number
  created_at: string
  updated_at: string
}

export interface ReviewDecisionResponse {
  review_task: ReviewTask
  execution: {
    id: number
    status: string
    external_reference: string | null
    error_message: string | null
  } | null
  follow_up_review_task: ReviewTask | null
}

export interface WorkflowRun {
  id: string
  thread_id: string
  user_id: number
  email_id: number
  status: WorkflowRunStatus
  current_node: string | null
  graph_version: string
  model_provider: string
  model_name: string
  prompt_versions: Record<string, unknown>
  agent_trace: Array<Record<string, unknown>>
  pending_review_task_id: string | null
  started_at: string
  finished_at: string | null
  error_code: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}
