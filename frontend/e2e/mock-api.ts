import type { Page, Route } from '@playwright/test'

type MockOptions = {
  empty?: boolean
  failPath?: string
  ambiguous?: boolean
}

const now = '2026-07-30T08:00:00+08:00'

const account = {
  id: 1,
  provider: '163',
  email_address: 'acceptance-test@163.com',
  email_address_masked: 'a***@163.com',
  imap_host: 'imap.163.com',
  imap_port: 993,
  imap_security: 'SSL',
  smtp_host: 'smtp.163.com',
  smtp_port: 465,
  smtp_security: 'SSL',
  is_active: true,
  auto_sync_enabled: false,
  sync_interval_minutes: 10,
  next_sync_at: null,
  last_auto_sync_at: null,
  inbox_uid_validity: 1001,
  last_synced_uid: 42,
  last_sync_at: now,
  last_sync_status: 'SUCCEEDED',
  last_sync_error: null,
  created_at: now,
  updated_at: now,
}

const interviewAnalysis = {
  id: 1,
  email_id: 1,
  version: 1,
  is_current: true,
  status: 'VALID',
  is_job_related: true,
  category: 'INTERVIEW',
  priority: 'HIGH',
  should_reply: true,
  classification_confidence: 0.98,
  extraction_confidence: 0.95,
  summary: '星河科技邀请候选人参加后端开发工程师一面。',
  company_name: '星河科技',
  position_name: '后端开发工程师',
  event_type: 'INTERVIEW',
  event_time: '2099-08-05T14:00:00+08:00',
  deadline_at: null,
  source_timezone: 'Asia/Shanghai',
  extraction_json: { raw_time_text: '8 月 5 日（周三）14:00' },
  evidence_json: { company_name: '星河科技', event_time: '8 月 5 日 14:00' },
  missing_fields: [],
  schema_version: 'extraction-v1',
  created_at: now,
}

const ambiguousAnalysis = {
  ...interviewAnalysis,
  id: 2,
  email_id: 2,
  status: 'PENDING_CONFIRMATION',
  event_time: null,
  summary: '招聘方希望下周另约时间，具体岗位和时间需要确认。',
  position_name: null,
  extraction_json: { raw_time_text: '下周找时间' },
  missing_fields: ['position_name', 'event_time', 'source_timezone'],
}

const emailRows = [
  {
    id: 1,
    account_id: 1,
    application_id: 1,
    subject: '星河科技后端开发工程师一面邀请',
    from_name: '星河科技招聘组',
    from_address: 'hr@example.test',
    to_recipients: [{ name: '测试候选人', address: 'acceptance-test@163.com' }],
    direction: 'RECEIVED',
    received_at: now,
    parse_status: 'SUCCEEDED',
    archive_status: 'NONE',
  },
  {
    id: 2,
    account_id: 1,
    application_id: null,
    subject: '下周沟通时间确认',
    from_name: '招聘专员',
    from_address: 'recruiter@example.test',
    to_recipients: [{ address: 'acceptance-test@163.com' }],
    direction: 'RECEIVED',
    received_at: '2026-07-29T18:00:00+08:00',
    parse_status: 'SUCCEEDED',
    archive_status: 'NONE',
  },
  {
    id: 3,
    account_id: 1,
    application_id: null,
    subject: '已发送：面试时间确认',
    from_name: '测试候选人',
    from_address: 'acceptance-test@163.com',
    to_recipients: [{ address: 'hr@example.test' }],
    direction: 'SENT',
    received_at: '2026-07-30T09:00:00+08:00',
    parse_status: 'SUCCEEDED',
    archive_status: 'NONE',
  },
]

const emailDetails: Record<number, Record<string, unknown>> = {
  1: {
    ...emailRows[0],
    message_id: '<e2e-interview@example.test>',
    cc_recipients: [],
    sent_at: null,
    plain_body: '您好，请参加一面。',
    html_sanitized:
      '<h2>面试邀请</h2><p>请于 8 月 5 日 14:00 参加线上面试。</p>' +
      '<a href="https://meeting.example.test/room">进入会议</a>' +
      '<img alt="远程跟踪图" data-jm-remote-src="http://127.0.0.1:4173/e2e-tracker.png">' +
      '<img alt="内嵌日程图" data-jm-cid="agenda-image">' +
      '<script>parent.__xssExecuted = true</script><img src=x onerror="parent.__xssExecuted=true">',
    attachment_metadata: [
      { filename: '面试安排.png', content_id: '<agenda-image>', content_type: 'image/png' },
      { filename: '岗位说明.pdf', content_type: 'application/pdf' },
    ],
    current_analysis: interviewAnalysis,
  },
  2: {
    ...emailRows[1],
    message_id: '<e2e-ambiguous@example.test>',
    cc_recipients: [],
    sent_at: null,
    plain_body: '下周找时间聊聊，岗位之后再确认。',
    html_sanitized: null,
    attachment_metadata: [],
    current_analysis: ambiguousAnalysis,
  },
  3: {
    ...emailRows[2],
    message_id: '<e2e-sent@example.test>',
    cc_recipients: [],
    sent_at: now,
    plain_body: '感谢邀请，我会准时参加。',
    html_sanitized: null,
    attachment_metadata: [],
    current_analysis: null,
  },
}

const applications = [
  {
    id: 1,
    user_id: 1,
    company_name: '星河科技',
    company_alias: null,
    position_name: '后端开发工程师',
    location: '上海',
    current_stage: 'INTERVIEW',
    interview_result: 'PENDING',
    status: 'ACTIVE',
    source: 'EMAIL',
    applied_at: '2026-07-20T10:00:00+08:00',
    contact_name: '招聘组',
    contact_email: 'hr@example.test',
    notes: '脱敏验收数据',
    version: 1,
    created_at: now,
    updated_at: now,
  },
  {
    id: 2,
    user_id: 1,
    company_name: '星河科技',
    company_alias: null,
    position_name: '平台开发工程师',
    location: '北京',
    current_stage: 'APPLIED',
    interview_result: null,
    status: 'ACTIVE',
    source: 'MANUAL',
    applied_at: '2026-07-22T10:00:00+08:00',
    contact_name: null,
    contact_email: null,
    notes: null,
    version: 1,
    created_at: now,
    updated_at: now,
  },
]

const tasks = [
  {
    id: 1,
    user_id: 1,
    application_id: 1,
    source_email_id: 1,
    task_type: 'INTERVIEW',
    interview_round: 1,
    title: '星河科技一面',
    description: '后端开发工程师技术面试',
    raw_time_text: '8 月 5 日（周三）14:00',
    start_at: '2099-08-05T14:00:00+08:00',
    deadline_at: null,
    source_timezone: 'Asia/Shanghai',
    location: '线上会议',
    meeting_url: 'https://meeting.example.test/room',
    status: 'CONFIRMED',
    version: 1,
    created_at: now,
    updated_at: now,
  },
  {
    id: 2,
    user_id: 1,
    application_id: null,
    source_email_id: 2,
    task_type: 'INTERVIEW',
    interview_round: null,
    title: '待确认沟通时间',
    description: '时间和岗位存在歧义，需人工确认。',
    raw_time_text: '下周找时间',
    start_at: null,
    deadline_at: null,
    source_timezone: null,
    location: null,
    meeting_url: null,
    status: 'PENDING',
    version: 1,
    created_at: now,
    updated_at: now,
  },
]

const reminders = [
  {
    id: 1,
    user_id: 1,
    task_id: 1,
    title: '星河科技一面即将开始',
    remind_at: '2099-08-05T13:30:00+08:00',
    event_at: '2099-08-05T14:00:00+08:00',
    status: 'DELIVERED',
    delivered_at: now,
    read_at: null,
    created_at: now,
    updated_at: now,
  },
]

const reviewTasks = [
  {
    id: 'review-create-task',
    user_id: 1,
    workflow_run_id: 'run-e2e',
    source_email_id: 1,
    application_id: 1,
    draft_id: null,
    action_type: 'CREATE_TASK',
    risk_level: 'MEDIUM',
    proposed_payload: {
      application_id: 1,
      title: '星河科技一面',
      task_type: 'INTERVIEW',
      start_at: '2099-08-05T14:00:00+08:00',
      raw_time_text: '8 月 5 日 14:00',
      source_timezone: 'Asia/Shanghai',
    },
    reviewed_payload: null,
    status: 'PENDING',
    decision_source: null,
    decision_reason: null,
    reviewed_at: null,
    resource_version: 1,
    version: 1,
    created_at: now,
    updated_at: now,
  },
  {
    id: 'review-send-reply',
    user_id: 1,
    workflow_run_id: 'run-e2e',
    source_email_id: 1,
    application_id: 1,
    draft_id: 1,
    action_type: 'SEND_REPLY',
    risk_level: 'HIGH',
    proposed_payload: {
      subject: 'Re: 星河科技后端开发工程师一面邀请',
      to_recipients: [{ address: 'hr@example.test' }],
      reviewed_body: '感谢邀请，我会准时参加。',
    },
    reviewed_payload: null,
    status: 'PENDING',
    decision_source: null,
    decision_reason: null,
    reviewed_at: null,
    resource_version: 1,
    version: 1,
    created_at: '2026-07-30T08:01:00+08:00',
    updated_at: '2026-07-30T08:01:00+08:00',
  },
]

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json; charset=utf-8',
    body: JSON.stringify(body),
  })
}

function pageResult<T>(items: T[], url: URL) {
  const offset = Number(url.searchParams.get('offset') ?? 0)
  const limit = Number(url.searchParams.get('limit') ?? 100)
  return {
    items: items.slice(offset, offset + limit),
    total: items.length,
    offset,
    limit,
  }
}

export async function installMockApi(page: Page, options: MockOptions = {}) {
  const state = {
    accounts: options.empty ? [] : [structuredClone(account)],
    emails: options.empty ? [] : structuredClone(emailRows),
    emailDetails: options.empty ? {} : structuredClone(emailDetails),
    applications: options.empty ? [] : structuredClone(applications),
    tasks: options.empty ? [] : structuredClone(tasks),
    reminders: options.empty ? [] : structuredClone(reminders),
    reviews: options.empty ? [] : structuredClone(reviewTasks),
    syncCount: 0,
    decisions: 0,
    lastDecisionPayload: null as Record<string, unknown> | null,
  }

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname.replace('/api/v1', '')
    const method = request.method()

    if (options.failPath && path === options.failPath) {
      return json(route, { detail: '验收故障注入：后端服务暂时不可用' }, 503)
    }
    if (method === 'GET' && path === '/email-accounts') return json(route, state.accounts)
    if (method === 'POST' && path === '/email-accounts') {
      const payload = request.postDataJSON()
      const created = {
        ...account,
        ...payload,
        id: 2,
        email_address_masked: 'n***@qq.com',
        is_active: false,
      }
      state.accounts.push(created)
      return json(route, created, 201)
    }
    const activeMatch = path.match(/^\/email-accounts\/(\d+)\/active$/)
    if (method === 'PATCH' && activeMatch) {
      const id = Number(activeMatch[1])
      const payload = request.postDataJSON()
      state.accounts.forEach((item) => {
        item.is_active = item.id === id ? payload.is_active : false
      })
      return json(route, state.accounts.find((item) => item.id === id))
    }
    const settingsMatch = path.match(/^\/email-accounts\/(\d+)\/sync-settings$/)
    if (method === 'PATCH' && settingsMatch) {
      const item = state.accounts.find((value) => value.id === Number(settingsMatch[1]))
      Object.assign(item ?? {}, request.postDataJSON())
      return json(route, item)
    }
    if (method === 'POST' && /\/test-connection$/.test(path)) {
      return json(route, {
        imap: { success: true, message: 'IMAP 连接成功' },
        smtp: { success: true, message: 'SMTP 连接成功' },
      })
    }
    if (method === 'POST' && /\/sync$/.test(path)) {
      state.syncCount += 1
      return json(route, {
        account_id: 1,
        folder: 'INBOX',
        uid_validity: 1001,
        examined: 1,
        created: state.syncCount === 1 ? 1 : 0,
        skipped: state.syncCount === 1 ? 0 : 1,
        failed: 0,
        created_email_ids: state.syncCount === 1 ? [1] : [],
      })
    }
    if (method === 'GET' && path === '/emails') return json(route, state.emails)
    if (method === 'GET' && path === '/emails/query') {
      return json(route, pageResult(state.emails, url))
    }
    const emailMatch = path.match(/^\/emails\/(\d+)$/)
    if (method === 'GET' && emailMatch) {
      return json(route, state.emailDetails[Number(emailMatch[1])] ?? {}, 200)
    }
    const archiveMatch = path.match(/^\/emails\/(\d+)\/(archive|restore)-review$/)
    if (method === 'POST' && archiveMatch) {
      const emailId = Number(archiveMatch[1])
      const restoring = archiveMatch[2] === 'restore'
      const detail = state.emailDetails[emailId]
      const task = {
        id: `review-${restoring ? 'restore' : 'archive'}-${emailId}`,
        user_id: 1,
        workflow_run_id: `run-${restoring ? 'restore' : 'archive'}-${emailId}`,
        source_email_id: emailId,
        application_id: Number(detail?.application_id) || null,
        draft_id: null,
        action_type: restoring ? 'RESTORE_EMAIL' : 'ARCHIVE_EMAIL',
        risk_level: 'MEDIUM',
        proposed_payload: {
          schema_version: 'email-move-review.v1',
          source_folder: restoring ? 'JobMailArchive' : 'INBOX',
          source_uid_validity: 1001,
          source_uid: 42,
          target_folder: restoring ? 'INBOX' : 'JobMailArchive',
        },
        reviewed_payload: null,
        status: 'PENDING',
        decision_source: null,
        decision_reason: null,
        reviewed_at: null,
        resource_version: 42,
        version: 1,
        created_at: now,
        updated_at: now,
      }
      state.reviews.push(task)
      if (!restoring && detail) detail.archive_status = 'PROPOSED'
      const listItem = state.emails.find((item) => item.id === emailId)
      if (!restoring && listItem) listItem.archive_status = 'PROPOSED'
      return json(route, task)
    }
    if (method === 'GET' && /\/attachments\/\d+$/.test(path)) {
      return route.fulfill({
        status: 200,
        contentType: 'image/png',
        body: Buffer.from(
          'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
          'base64',
        ),
      })
    }
    if (method === 'POST' && /\/workflow-runs$/.test(path)) {
      return json(route, {
        id: 'run-e2e',
        thread_id: 'thread-e2e',
        user_id: 1,
        email_id: 1,
        status: 'WAITING_REVIEW',
        current_node: 'application_review',
        graph_version: 'v1',
        model_provider: 'stub',
        model_name: 'deterministic-e2e',
        prompt_versions: {},
        agent_trace: [],
        pending_review_task_id: 'review-create-task',
        started_at: now,
        finished_at: null,
        error_code: null,
        error_message: null,
        created_at: now,
        updated_at: now,
      })
    }
    if (method === 'GET' && path === '/job-applications') {
      return json(route, state.applications)
    }
    if (method === 'GET' && path === '/job-applications/query') {
      return json(route, pageResult(state.applications, url))
    }
    if (method === 'POST' && path === '/job-applications') {
      const created = {
        ...applications[0],
        ...request.postDataJSON(),
        id: state.applications.length + 1,
        current_stage: 'APPLIED',
        interview_result: null,
        source: 'MANUAL',
      }
      state.applications.push(created)
      return json(route, created, 201)
    }
    const stageTransitionMatch = path.match(
      /^\/job-applications\/(\d+)\/stage-transitions$/,
    )
    if (method === 'POST' && stageTransitionMatch) {
      const item = state.applications.find(
        (value) => value.id === Number(stageTransitionMatch[1]),
      )
      const payload = request.postDataJSON()
      if (item) {
        item.current_stage = payload.proposed_stage
        item.status = ['REJECTED', 'WITHDRAWN'].includes(payload.proposed_stage)
          ? payload.proposed_stage === 'REJECTED'
            ? 'CLOSED'
            : 'WITHDRAWN'
          : 'ACTIVE'
        item.version += 1
      }
      return json(route, item)
    }
    const interviewResultMatch = path.match(
      /^\/job-applications\/(\d+)\/interview-result$/,
    )
    if (method === 'POST' && interviewResultMatch) {
      const item = state.applications.find(
        (value) => value.id === Number(interviewResultMatch[1]),
      )
      const payload = request.postDataJSON()
      if (item) {
        item.interview_result = payload.result
        item.status = payload.result === 'FAILED' ? 'CLOSED' : 'ACTIVE'
        item.version += 1
        if (['PASSED', 'FAILED'].includes(payload.result)) {
          state.tasks
            .filter((task) => task.application_id === item.id && task.task_type === 'INTERVIEW')
            .forEach((task) => {
              if (['PENDING', 'CONFIRMED'].includes(task.status)) task.status = 'COMPLETED'
            })
        }
      }
      return json(route, item)
    }
    const nextInterviewMatch = path.match(
      /^\/job-applications\/(\d+)\/next-interview$/,
    )
    if (method === 'POST' && nextInterviewMatch) {
      const item = state.applications.find(
        (value) => value.id === Number(nextInterviewMatch[1]),
      )
      const payload = request.postDataJSON()
      const currentRound = Math.max(
        0,
        ...state.tasks
          .filter((task) => task.application_id === item?.id && task.task_type === 'INTERVIEW')
          .map((task) => task.interview_round ?? 0),
      )
      const task = {
        ...tasks[0],
        ...payload,
        id: Math.max(0, ...state.tasks.map((value) => value.id)) + 1,
        application_id: item?.id ?? null,
        source_email_id: null,
        interview_round: currentRound + 1,
        status: 'CONFIRMED',
        version: 1,
        created_at: now,
        updated_at: now,
      }
      if (item) {
        item.interview_result = 'PENDING'
        item.status = 'ACTIVE'
        item.version += 1
      }
      state.tasks.push(task)
      return json(route, { application: item, task })
    }
    const applicationMatch = path.match(/^\/job-applications\/(\d+)$/)
    if (method === 'PATCH' && applicationMatch) {
      const item = state.applications.find((value) => value.id === Number(applicationMatch[1]))
      Object.assign(item ?? {}, request.postDataJSON())
      if (item) item.version += 1
      return json(route, item)
    }
    if (method === 'GET' && /\/job-applications\/\d+\/events$/.test(path)) {
      return json(route, {
        items: [
          {
            id: 1,
            application_id: 1,
            source_email_id: 1,
            workflow_run_id: 'run-e2e',
            event_type: 'STAGE_CHANGED',
            previous_stage: 'APPLIED',
            proposed_stage: 'INTERVIEW',
            confirmed_stage: 'INTERVIEW',
            raw_time_text: '8 月 5 日 14:00',
            event_at: '2099-08-05T14:00:00+08:00',
            source_timezone: 'Asia/Shanghai',
            details: null,
            created_at: now,
          },
        ],
        total: 1,
        offset: 0,
        limit: 100,
      })
    }
    if (method === 'GET' && path === '/tasks') return json(route, state.tasks)
    if (method === 'GET' && path === '/tasks/query') {
      return json(route, pageResult(state.tasks, url))
    }
    const taskMatch = path.match(/^\/tasks\/(\d+)$/)
    if (method === 'PATCH' && taskMatch) {
      const item = state.tasks.find((value) => value.id === Number(taskMatch[1]))
      Object.assign(item ?? {}, request.postDataJSON())
      if (item) item.version += 1
      return json(route, item)
    }
    const withdrawFromTaskMatch = path.match(/^\/tasks\/(\d+)\/withdraw-application$/)
    if (method === 'POST' && withdrawFromTaskMatch) {
      const item = state.tasks.find((value) => value.id === Number(withdrawFromTaskMatch[1]))
      const application = state.applications.find((value) => value.id === item?.application_id)
      if (application) {
        application.current_stage = 'WITHDRAWN'
        application.status = 'WITHDRAWN'
        application.version += 1
        state.tasks
          .filter((task) => task.application_id === application.id)
          .forEach((task) => {
            if (['PENDING', 'CONFIRMED'].includes(task.status)) task.status = 'CANCELLED'
          })
      }
      return json(route, item)
    }
    if (method === 'GET' && path === '/reminders') return json(route, state.reminders)
    const reminderMatch = path.match(/^\/reminders\/(\d+)\/read$/)
    if (method === 'PATCH' && reminderMatch) {
      const item = state.reminders.find((value) => value.id === Number(reminderMatch[1]))
      if (item) {
        item.status = 'READ'
        item.read_at = now
        state.reminders = state.reminders.filter((value) => value.id !== item.id)
      }
      return json(route, item)
    }
    if (method === 'GET' && path === '/review-tasks') return json(route, state.reviews)
    if (method === 'GET' && path === '/review-tasks/query') {
      return json(route, pageResult(state.reviews, url))
    }
    const reviewDetailMatch = path.match(/^\/review-tasks\/([^/]+)$/)
    if (method === 'GET' && reviewDetailMatch) {
      return json(route, state.reviews.find((item) => item.id === reviewDetailMatch[1]))
    }
    const decisionMatch = path.match(/^\/review-tasks\/([^/]+)\/decision$/)
    if (method === 'POST' && decisionMatch) {
      state.decisions += 1
      if (state.decisions > 1) {
        return json(route, { detail: '审核任务已处理，请勿重复提交' }, 409)
      }
      const item = state.reviews.find((value) => value.id === decisionMatch[1])
      const payload = request.postDataJSON()
      state.lastDecisionPayload = structuredClone(payload)
      if (item) {
        item.status = payload.approve ? 'SUCCEEDED' : 'REJECTED'
        item.reviewed_payload = payload.reviewed_payload
        item.decision_reason = payload.reason
        item.reviewed_at = now
        item.version += 1
        const detail = item.source_email_id
          ? state.emailDetails[item.source_email_id]
          : undefined
        const listItem = state.emails.find((value) => value.id === item.source_email_id)
        if (item.action_type === 'ARCHIVE_EMAIL') {
          const status = payload.approve ? 'ARCHIVED' : 'NONE'
          if (detail) detail.archive_status = status
          if (listItem) listItem.archive_status = status
        }
        if (item.action_type === 'RESTORE_EMAIL' && payload.approve) {
          if (detail) detail.archive_status = 'RESTORED'
          if (listItem) listItem.archive_status = 'RESTORED'
        }
      }
      return json(route, {
        review_task: item,
        execution: payload.approve
          ? { id: 1, status: 'SUCCEEDED', external_reference: null, error_message: null }
          : null,
        follow_up_review_task:
          payload.approve && item?.id === 'review-create-task'
            ? state.reviews.find((review) => review.id === 'review-send-reply')
            : null,
      })
    }
    return json(route, { detail: `未配置的 E2E API：${method} ${path}` }, 501)
  })

  return state
}
