import type { ReviewActionType, ReviewTask } from '@/types/api'

const visibleFields: Record<ReviewActionType, readonly string[]> = {
  CREATE_APPLICATION: [
    'company_name',
    'position_name',
    'proposed_stage',
    'interview_result',
    'summary',
  ],
  LINK_APPLICATION: [
    'company_name',
    'position_name',
    'proposed_stage',
    'interview_result',
    'summary',
    'stage_validation',
  ],
  UPDATE_APPLICATION_STAGE: [
    'company_name',
    'position_name',
    'previous_stage',
    'proposed_stage',
    'interview_result',
    'validation',
  ],
  CREATE_TASK: [
    'company_name',
    'position_name',
    'title',
    'task_type',
    'interview_round',
    'start_at',
    'deadline_at',
    'location',
    'meeting_url',
    'raw_time_text',
    'source_timezone',
  ],
  UPDATE_TASK: [
    'title',
    'task_type',
    'start_at',
    'deadline_at',
    'location',
    'meeting_url',
    'raw_time_text',
    'source_timezone',
  ],
  SEND_REPLY: [
    'body',
    'generated_body',
    'reviewed_body',
    'subject',
    'to_recipients',
    'cc_recipients',
  ],
  UPDATE_INTERVIEW_RESULT: [
    'company_name',
    'position_name',
    'round_number',
    'result',
    'summary',
  ],
  ARCHIVE_EMAIL: ['source_folder', 'target_folder'],
  RESTORE_EMAIL: ['source_folder', 'target_folder'],
}

export function visibleReviewPayloadEntries(
  task: ReviewTask,
): Array<[string, unknown]> {
  const payload = task.proposed_payload
  return visibleFields[task.action_type]
    .filter((key) => Object.prototype.hasOwnProperty.call(payload, key))
    .map((key) => [key, payload[key]])
}
