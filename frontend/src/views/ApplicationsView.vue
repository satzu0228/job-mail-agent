<script setup lang="ts">
import { Plus, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'

import { applicationApi } from '@/api'
import { getApiErrorMessage, isVersionConflict } from '@/api/http'
import ApplicationActionBar from '@/components/applications/ApplicationActionBar.vue'
import { useApplicationStore } from '@/stores/applications'
import { useMailStore } from '@/stores/mail'
import { useTaskStore } from '@/stores/tasks'
import {
  eventTypeLabels,
  roundResultMeta,
  stageMeta,
  taskStatusMeta,
  taskTypeMeta,
} from '@/utils/dictionaries'
import {
  appliedDateTime,
  dateInputValue,
  formatDate,
  formatDateTime,
  taskTime,
} from '@/utils/format'
import type {
  ApplicationEvent,
  ApplicationStage,
  EmailListItem,
  InterviewResult,
  InterviewRound,
  JobApplication,
  JobApplicationCreate,
  OfferResult,
  Task,
} from '@/types/api'

type ProgressFilter = 'all' | 'active' | 'closed'

const applicationStore = useApplicationStore()
const taskStore = useTaskStore()
const mailStore = useMailStore()
const { applications, loading } = storeToRefs(applicationStore)
const { tasks } = storeToRefs(taskStore)
const { emails } = storeToRefs(mailStore)
const interviewRounds = ref<InterviewRound[]>([])
const keyword = ref('')
const progressFilter = ref<ProgressFilter>('all')
const stageFilter = ref('')
const drawerVisible = ref(false)
const createVisible = ref(false)
const stageVisible = ref(false)
const resultVisible = ref(false)
const offerVisible = ref(false)
const reopenVisible = ref(false)
const nextInterviewVisible = ref(false)
const selected = ref<JobApplication | null>(null)
const applicationEvents = ref<ApplicationEvent[]>([])
const loadingEvents = ref(false)
const saving = ref(false)
const transitioningStage = ref(false)
const savingResult = ref(false)
const savingOffer = ref(false)
const reopening = ref(false)
const schedulingNextInterview = ref(false)
const createFormRef = ref<FormInstance>()

const createForm = reactive<JobApplicationCreate>({
  company_name: '',
  position_name: '',
  location: null,
  applied_at: null,
  contact_name: null,
  contact_email: null,
  notes: null,
})

const editForm = reactive({
  company_name: '',
  position_name: '',
  location: '',
  applied_at: '',
  contact_name: '',
  contact_email: '',
  notes: '',
})

const stageForm = reactive({
  proposed_stage: null as ApplicationStage | null,
  reason: '',
})

const resultForm = reactive({
  result: null as InterviewResult | null,
  reason: '',
})

const offerForm = reactive({
  result: null as OfferResult | null,
  reason: '',
})

const roundResultVisible = ref(false)
const savingRoundResult = ref(false)
const roundResultForm = reactive({
  roundNumber: 0,
  roundLabel: '',
  result: null as InterviewResult | null,
  reason: '',
})

const reopenForm = reactive({
  target_stage: 'APPLIED' as Exclude<ApplicationStage, 'REJECTED' | 'WITHDRAWN'>,
  reason: '',
})

const nextInterviewForm = reactive({
  title: '',
  start_at: '',
  deadline_at: '',
  location: '',
  meeting_url: '',
  description: '',
  reason: '',
})

const interviewResultOptions: Array<{
  value: InterviewResult
  label: string
  description: string
}> = [
  { value: 'PASSED', label: '已通过', description: '本轮面试通过，继续等待下一轮或 Offer' },
  { value: 'FAILED', label: '未通过', description: '本轮面试未通过，申请归入已结束' },
  { value: 'PENDING', label: '待确认', description: '尚未收到明确结果，继续等待通知' },
]

const availableStages = computed(() =>
  selected.value?.allowed_transitions ?? [],
)

const rules: FormRules = {
  company_name: [{ required: true, message: '请输入公司名称', trigger: 'blur' }],
  position_name: [{ required: true, message: '请输入投递岗位', trigger: 'blur' }],
}

const rows = computed(() => {
  const normalized = keyword.value.trim().toLowerCase()
  return applications.value.filter((application) => {
    const isClosed = application.status !== 'ACTIVE'
    if (progressFilter.value === 'active' && isClosed) return false
    if (progressFilter.value === 'closed' && !isClosed) return false
    if (stageFilter.value && application.current_stage !== stageFilter.value) return false
    if (!normalized) return true
    return [application.company_name, application.position_name, application.location]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(normalized))
  })
})

const emptyMessage = computed(() => {
  if (keyword.value || stageFilter.value) return '没有符合筛选条件的申请'
  if (progressFilter.value === 'closed') return '暂无已结束的申请'
  if (progressFilter.value === 'active') return '暂无进行中的申请'
  return '还没有求职申请'
})

const showFirstApplicationAction = computed(
  () =>
    applications.value.length === 0 &&
    progressFilter.value === 'all' &&
    !keyword.value &&
    !stageFilter.value,
)

function relatedTasks(id: number): Task[] {
  return tasks.value
    .filter((task) => task.application_id === id)
    .sort((a, b) => String(taskTime(a)).localeCompare(String(taskTime(b))))
}

function stageLabel(stage: JobApplication['current_stage']): string {
  return stageMeta[stage].label
}

async function handleApplicationCommandError(error: unknown) {
  if (isVersionConflict(error) && selected.value) {
    selected.value = await applicationStore.refresh(selected.value.id)
    ElMessage.warning('申请状态已被更新，请确认最新内容后重新提交')
    return
  }
  ElMessage.error(getApiErrorMessage(error))
}

function stageType(stage: JobApplication['current_stage']) {
  return stageMeta[stage].type
}

function interviewRoundLabel(round: number | null): string {
  if (!round) return '面试'
  const numerals = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
  return round <= numerals.length ? `${numerals[round - 1]}面` : `第 ${round} 轮面试`
}

function interviewTask(applicationId: number): Task | undefined {
  return relatedTasks(applicationId)
    .filter((task) => task.task_type === 'INTERVIEW' && task.status !== 'CANCELLED')
    .sort((a, b) => {
      const roundDelta = (b.interview_round ?? 0) - (a.interview_round ?? 0)
      if (roundDelta) return roundDelta
      return String(taskTime(b)).localeCompare(String(taskTime(a)))
    })[0]
}

function nextInterviewRound(applicationId: number): number {
  const rounds = relatedTasks(applicationId)
    .filter((task) => task.task_type === 'INTERVIEW')
    .map((task) => task.interview_round ?? 0)
  return Math.max(0, ...rounds) + 1
}

function applicationStageLabel(application: JobApplication): string {
  if (application.current_stage !== 'INTERVIEW') return stageLabel(application.current_stage)
  return interviewRoundLabel(interviewTask(application.id)?.interview_round ?? null)
}

function taskLabel(task: Task): string {
  return task.task_type === 'INTERVIEW'
    ? interviewRoundLabel(task.interview_round)
    : task.title
}

function interviewResultLabelFromDetails(value: unknown): string {
  return value === 'PASSED' ? '已通过' : value === 'FAILED' ? '未通过' : '待确认'
}

function applicationEventSummary(event: ApplicationEvent): string {
  if (event.event_type === 'INTERVIEW_RESULT_CHANGED') {
    const details = event.details ?? {}
    const round = typeof details.interview_round === 'number'
      ? interviewRoundLabel(details.interview_round)
      : '面试'
    return `${round}结果：${interviewResultLabelFromDetails(details.interview_result)}`
  }
  if (event.event_type === 'NEXT_INTERVIEW_SCHEDULED') {
    const round = typeof event.details?.interview_round === 'number'
      ? interviewRoundLabel(event.details.interview_round)
      : '下一轮面试'
    return `已登记${round}，本轮结果恢复为待确认`
  }
  if (event.event_type === 'APPLICATION_WITHDRAWN_FROM_CALENDAR') {
    return '已撤回申请，并取消未完成面试日程'
  }
  return event.confirmed_stage
    ? `${event.previous_stage ? stageLabel(event.previous_stage) : '未设置'} → ${stageLabel(event.confirmed_stage)}`
    : event.raw_time_text || '已记录申请事件'
}

function interviewResultLabel(result: InterviewResult | null): string {
  return result === 'PASSED' ? '已通过' : result === 'FAILED' ? '未通过' : '待确认'
}

function interviewResultClass(result: InterviewResult | null): string {
  return result === 'PASSED' ? 'is-passed' : result === 'FAILED' ? 'is-failed' : 'is-pending'
}

function offerResultLabel(result: OfferResult | null): string {
  if (result === 'ACCEPTED') return '已接受 Offer'
  if (result === 'DECLINED') return '已谢绝 Offer'
  return '待确认 Offer'
}

function offerResultClass(result: OfferResult | null): string {
  return result === 'ACCEPTED' ? 'is-passed' : result === 'DECLINED' ? 'is-failed' : 'is-pending'
}

function relatedEmails(id: number): EmailListItem[] {
  return emails.value
    .filter((email) => email.application_id === id)
    .sort((a, b) => String(b.received_at).localeCompare(String(a.received_at)))
}

function nextTask(applicationId: number): Task | undefined {
  const now = Date.now()
  return relatedTasks(applicationId).find((task) => {
    const value = taskTime(task)
    return (
      value &&
      new Date(value).getTime() >= now &&
      task.status !== 'COMPLETED' &&
      task.status !== 'CANCELLED'
    )
  })
}

async function loadData() {
  try {
    await Promise.all([
      applicationStore.loadPage({ offset: 0, limit: 50 }),
      taskStore.refreshRange({ offset: 0, limit: 100 }),
      mailStore.loadPage({ offset: 0, limit: 50 }),
    ])
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

async function openApplication(application: JobApplication) {
  selected.value = application
  Object.assign(editForm, {
    company_name: application.company_name,
    position_name: application.position_name,
    location: application.location ?? '',
    applied_at: dateInputValue(application.applied_at),
    contact_name: application.contact_name ?? '',
    contact_email: application.contact_email ?? '',
    notes: application.notes ?? '',
  })
  drawerVisible.value = true
  loadingEvents.value = true
  try {
    const details = await applicationStore.loadDetails(application.id)
    applicationEvents.value = details.events
    interviewRounds.value = details.rounds
  } catch (error) {
    applicationEvents.value = []
    interviewRounds.value = []
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    loadingEvents.value = false
  }
}

async function saveApplication() {
  if (!selected.value) return
  saving.value = true
  try {
    const updated = await applicationApi.update(selected.value.id, {
      version: selected.value.version,
      company_name: editForm.company_name,
      position_name: editForm.position_name,
      location: editForm.location || null,
      applied_at: appliedDateTime(editForm.applied_at),
      contact_name: editForm.contact_name || null,
      contact_email: editForm.contact_email || null,
      notes: editForm.notes || null,
    })
    applicationStore.upsert(updated)
    selected.value = updated
    ElMessage.success('申请信息已保存')
  } catch (error) {
    await handleApplicationCommandError(error)
  } finally {
    saving.value = false
  }
}

function openStageTransition() {
  stageForm.proposed_stage = null
  stageForm.reason = ''
  stageVisible.value = true
}

async function transitionStage() {
  if (!selected.value || !stageForm.proposed_stage) {
    ElMessage.warning('请选择目标阶段')
    return
  }
  if (!stageForm.reason.trim()) {
    ElMessage.warning('请填写阶段变更说明')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认将“${selected.value.company_name} · ${selected.value.position_name}”从“${stageLabel(selected.value.current_stage)}”更新为“${stageLabel(stageForm.proposed_stage)}”？`,
      '确认更新阶段',
      {
        confirmButtonText: '确认更新',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  transitioningStage.value = true
  try {
    const updated = await applicationApi.transitionStage(selected.value.id, {
      version: selected.value.version,
      proposed_stage: stageForm.proposed_stage,
      reason: stageForm.reason.trim(),
    })
    applicationStore.upsert(updated)
    selected.value = updated
    applicationEvents.value = (await applicationApi.events(updated.id)).items
    stageVisible.value = false
    ElMessage.success('申请阶段已更新')
  } catch (error) {
    await handleApplicationCommandError(error)
  } finally {
    transitioningStage.value = false
  }
}

function openInterviewResult(application: JobApplication) {
  selected.value = application
  resultForm.result = application.interview_result ?? 'PENDING'
  resultForm.reason = ''
  resultVisible.value = true
}

async function updateInterviewResult() {
  if (!selected.value || !resultForm.result) return
  if (!resultForm.reason.trim()) {
    ElMessage.warning('请说明结果来源')
    return
  }
  savingResult.value = true
  try {
    const updated = await applicationApi.updateInterviewResult(selected.value.id, {
      version: selected.value.version,
      result: resultForm.result,
      reason: resultForm.reason.trim(),
    })
    applicationStore.upsert(updated)
    selected.value = updated
    if (updated.interview_result === 'PASSED') drawerVisible.value = true
    if (drawerVisible.value) {
      applicationEvents.value = (await applicationApi.events(updated.id)).items
    }
    resultVisible.value = false
    ElMessage.success(`面试结果已更新为“${interviewResultLabel(updated.interview_result)}”`)
  } catch (error) {
    await handleApplicationCommandError(error)
  } finally {
    savingResult.value = false
  }
}

function openNextInterview() {
  if (!selected.value) return
  const round = nextInterviewRound(selected.value.id)
  Object.assign(nextInterviewForm, {
    title: `${selected.value.company_name} ${interviewRoundLabel(round)}`,
    start_at: '',
    deadline_at: '',
    location: selected.value.location ?? '',
    meeting_url: '',
    description: '',
    reason: '',
  })
  nextInterviewVisible.value = true
}

function openRoundResult(round: InterviewRound) {
  roundResultForm.roundNumber = round.round_number
  roundResultForm.roundLabel = interviewRoundLabel(round.round_number)
  roundResultForm.result = round.result
  roundResultForm.reason = ''
  roundResultVisible.value = true
}

async function updateRoundResult() {
  if (!selected.value || !roundResultForm.result) return
  if (!roundResultForm.reason.trim()) {
    ElMessage.warning('请填写修改原因')
    return
  }
  savingRoundResult.value = true
  try {
    const response = await applicationApi.updateInterviewRoundResult(selected.value.id, {
      version: selected.value.version,
      round_number: roundResultForm.roundNumber,
      result: roundResultForm.result,
      reason: roundResultForm.reason.trim(),
    })
    applicationStore.upsert(response.application)
    selected.value = response.application
    // 刷新轮次和事件
    const [rounds, events] = await Promise.all([
      applicationApi.listInterviewRounds(selected.value.id),
      applicationApi.events(selected.value.id),
    ])
    interviewRounds.value = rounds
    applicationEvents.value = events.items
    roundResultVisible.value = false
    ElMessage.success(`${roundResultForm.roundLabel}结果已更新为"${interviewResultLabel(response.round.result)}"`)
  } catch (error) {
    await handleApplicationCommandError(error)
  } finally {
    savingRoundResult.value = false
  }
}

function openOfferStage() {
  stageForm.proposed_stage = 'OFFER'
  stageForm.reason = ''
  stageVisible.value = true
}

async function scheduleNextInterview() {
  if (!selected.value) return
  if (!nextInterviewForm.title.trim() || !nextInterviewForm.start_at) {
    ElMessage.warning('请填写下一轮面试标题和开始时间')
    return
  }
  if (!nextInterviewForm.reason.trim()) {
    ElMessage.warning('请说明下一轮安排的来源')
    return
  }
  schedulingNextInterview.value = true
  try {
    const response = await applicationApi.scheduleNextInterview(selected.value.id, {
      version: selected.value.version,
      title: nextInterviewForm.title.trim(),
      description: nextInterviewForm.description.trim() || null,
      start_at: new Date(nextInterviewForm.start_at).toISOString(),
      deadline_at: nextInterviewForm.deadline_at
        ? new Date(nextInterviewForm.deadline_at).toISOString()
        : null,
      source_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai',
      location: nextInterviewForm.location.trim() || null,
      meeting_url: nextInterviewForm.meeting_url.trim() || null,
      reason: nextInterviewForm.reason.trim(),
    })
    applicationStore.upsert(response.application)
    selected.value = response.application
    taskStore.upsert(response.task)
    applicationEvents.value = (await applicationApi.events(response.application.id)).items
    nextInterviewVisible.value = false
    ElMessage.success(`${interviewRoundLabel(response.task.interview_round)}已登记`)
  } catch (error) {
    await handleApplicationCommandError(error)
  } finally {
    schedulingNextInterview.value = false
  }
}

function openOfferResult(application: JobApplication) {
  selected.value = application
  offerForm.result = application.offer_result ?? 'PENDING'
  offerForm.reason = ''
  offerVisible.value = true
}

async function updateOfferResult() {
  if (!selected.value || !offerForm.result) return
  if (!offerForm.reason.trim()) {
    ElMessage.warning('请说明 Offer 结果来源')
    return
  }
  savingOffer.value = true
  try {
    const updated = await applicationApi.updateOfferResult(selected.value.id, {
      version: selected.value.version,
      result: offerForm.result,
      reason: offerForm.reason.trim(),
    })
    applicationStore.upsert(updated)
    selected.value = updated
    if (drawerVisible.value) {
      applicationEvents.value = (await applicationApi.events(updated.id)).items
    }
    offerVisible.value = false
    ElMessage.success(`Offer 结果已更新为“${offerResultLabel(updated.offer_result)}”`)
  } catch (error) {
    await handleApplicationCommandError(error)
  } finally {
    savingOffer.value = false
  }
}

function openReopenApplication() {
  if (!selected.value) return
  // 仅允许恢复到非终态阶段，优先沿用关闭时的阶段。
  const reopenable = ['APPLIED', 'ASSESSMENT', 'INTERVIEW', 'OFFER'] as const
  const stage = selected.value.current_stage
  reopenForm.target_stage = reopenable.includes(stage as typeof reopenable[number])
    ? (stage as typeof reopenable[number])
    : 'APPLIED'
  reopenForm.reason = ''
  reopenVisible.value = true
}

async function reopenApplication() {
  if (!selected.value) return
  if (!reopenForm.reason.trim()) {
    ElMessage.warning('请填写重新打开原因')
    return
  }
  reopening.value = true
  try {
    const updated = await applicationApi.reopen(selected.value.id, {
      version: selected.value.version,
      target_stage: reopenForm.target_stage,
      reason: reopenForm.reason.trim(),
    })
    applicationStore.upsert(updated)
    selected.value = updated
    applicationEvents.value = (await applicationApi.events(updated.id)).items
    reopenVisible.value = false
    ElMessage.success('申请已重新打开')
  } catch (error) {
    await handleApplicationCommandError(error)
  } finally {
    reopening.value = false
  }
}

async function createApplication() {
  if (!(await createFormRef.value?.validate())) return
  saving.value = true
  try {
    await applicationApi.create({
      ...createForm,
      applied_at: appliedDateTime(createForm.applied_at),
    })
    ElMessage.success('求职申请已创建')
    createVisible.value = false
    Object.assign(createForm, {
      company_name: '',
      position_name: '',
      location: null,
      applied_at: null,
      contact_name: null,
      contact_email: null,
      notes: null,
    })
    await loadData()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    saving.value = false
  }
}

onMounted(loadData)
</script>

<template>
  <div class="page-shell applications-page">
    <div class="page-toolbar">
      <div class="toolbar-group">
        <div class="progress-tabs">
          <button
            v-for="item in [
              { value: 'all', label: '全部' },
              { value: 'active', label: '进行中' },
              { value: 'closed', label: '已结束' },
            ]"
            :key="item.value"
            type="button"
            :class="{ active: progressFilter === item.value }"
            @click="progressFilter = item.value as ProgressFilter"
          >
            {{ item.label }}
          </button>
        </div>
        <span class="result-count">{{ rows.length }} 项申请</span>
      </div>
      <div class="toolbar-group">
        <ElInput
          v-model="keyword"
          class="search-input"
          clearable
          :prefix-icon="Search"
          placeholder="搜索公司或岗位"
        />
        <ElSelect v-model="stageFilter" clearable placeholder="全部阶段" class="stage-select">
          <ElOption
            v-for="(meta, value) in stageMeta"
            :key="value"
            :label="meta.label"
            :value="value"
          />
        </ElSelect>
        <ElButton type="primary" :icon="Plus" @click="createVisible = true">新建申请</ElButton>
      </div>
    </div>

    <section class="surface progress-table">
      <ElTable
        v-loading="loading"
        :data="rows"
        height="100%"
        row-class-name="clickable-row"
        @row-click="openApplication"
      >
        <ElTableColumn prop="company_name" label="公司" fixed min-width="190" show-overflow-tooltip>
          <template #default="{ row }">
            <strong class="company-name">{{ row.company_name }}</strong>
          </template>
        </ElTableColumn>
        <ElTableColumn
          prop="position_name"
          label="投递岗位"
          fixed
          min-width="190"
          show-overflow-tooltip
        />
        <ElTableColumn label="当前阶段" width="120">
          <template #default="{ row }">
            <ElTag :type="stageType(row.current_stage)" effect="light">
              {{ applicationStageLabel(row) }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="面试结果" width="126">
          <template #default="{ row }">
            <button
              v-if="row.current_stage === 'INTERVIEW'"
              type="button"
              class="result-pill"
              :class="interviewResultClass(row.interview_result)"
              @click.stop="openInterviewResult(row)"
            >
              <span />{{ interviewResultLabel(row.interview_result) }}
            </button>
            <span v-else class="quiet">—</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="Offer 结果" width="136">
          <template #default="{ row }">
            <button
              v-if="row.current_stage === 'OFFER'"
              type="button"
              class="result-pill"
              :class="offerResultClass(row.offer_result)"
              @click.stop="openOfferResult(row)"
            >
              <span />{{ offerResultLabel(row.offer_result) }}
            </button>
            <span v-else class="quiet">—</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="投递时间" width="126" sortable>
          <template #default="{ row }">{{ formatDate(row.applied_at) }}</template>
        </ElTableColumn>
        <ElTableColumn label="下一安排" min-width="180">
          <template #default="{ row }">
            <div v-if="nextTask(row.id)" class="next-task">
              <span
                class="task-dot"
                :style="{ background: taskTypeMeta[nextTask(row.id)!.task_type].color }"
              />
              <div>
                <strong>{{ taskLabel(nextTask(row.id)!) }}</strong>
                <span>{{ formatDateTime(taskTime(nextTask(row.id)!)) }}</span>
              </div>
            </div>
            <span
              v-else-if="row.current_stage === 'INTERVIEW' && row.interview_result === 'PASSED'"
              class="waiting-next"
            >
              下一阶段：待确认
            </span>
            <span v-else class="quiet">—</span>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="location" label="所在地" width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.location || '—' }}</template>
        </ElTableColumn>
        <ElTableColumn prop="contact_name" label="联系人" width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.contact_name || '—' }}</template>
        </ElTableColumn>
        <ElTableColumn label="关联邮件" width="100" align="center">
          <template #default="{ row }">{{ relatedEmails(row.id).length }}</template>
        </ElTableColumn>
        <ElTableColumn label="最近更新" width="132">
          <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
        </ElTableColumn>
        <template #empty>
          <div class="table-empty">
            <p>{{ emptyMessage }}</p>
            <ElButton v-if="showFirstApplicationAction" type="primary" plain @click="createVisible = true">
              新建第一项申请
            </ElButton>
          </div>
        </template>
      </ElTable>
    </section>

    <ElDrawer
      v-model="drawerVisible"
      size="min(560px, 92vw)"
      :title="selected ? `${selected.company_name} · ${selected.position_name}` : '申请详情'"
    >
      <div v-if="selected" class="application-drawer">
        <div class="drawer-stage">
          <div class="stage-identity">
            <span>当前进度</span>
            <strong>{{ applicationStageLabel(selected) }}</strong>
            <button
              v-if="selected.current_stage === 'INTERVIEW'"
              type="button"
              class="result-pill"
              :class="interviewResultClass(selected.interview_result)"
              @click="openInterviewResult(selected)"
            >
              <span />{{ interviewResultLabel(selected.interview_result) }}
            </button>
            <button
              v-if="selected.current_stage === 'OFFER'"
              type="button"
              class="result-pill"
              :class="offerResultClass(selected.offer_result)"
              @click="openOfferResult(selected)"
            >
              <span />{{ offerResultLabel(selected.offer_result) }}
            </button>
          </div>
          <p v-if="interviewTask(selected.id)">
            {{ formatDateTime(taskTime(interviewTask(selected.id)!)) }}
          </p>
          <ApplicationActionBar
            :application="selected"
            @transition="openStageTransition"
            @reopen="openReopenApplication"
          />
        </div>

        <div
          v-if="selected.current_stage === 'INTERVIEW' && selected.interview_result === 'PASSED'"
          class="next-step-card"
        >
          <div>
            <strong>{{ applicationStageLabel(selected) }}已通过，下一阶段待确认</strong>
            <span>适用于每一轮面试：收到新安排后登记下一轮，确认录用流程后再进入 Offer。</span>
          </div>
          <div class="next-step-actions">
            <ElButton type="primary" @click="openNextInterview">登记下一轮面试</ElButton>
            <ElButton plain @click="openOfferStage">进入 Offer</ElButton>
          </div>
        </div>

        <ElTabs>
          <ElTabPane label="基本信息">
            <ElForm :model="editForm" label-position="top" class="drawer-form">
              <div class="form-grid">
                <ElFormItem label="公司名称">
                  <ElInput v-model="editForm.company_name" />
                </ElFormItem>
                <ElFormItem label="投递岗位">
                  <ElInput v-model="editForm.position_name" />
                </ElFormItem>
                <ElFormItem label="所在地">
                  <ElInput v-model="editForm.location" />
                </ElFormItem>
                <ElFormItem label="投递时间">
                  <ElDatePicker
                    v-model="editForm.applied_at"
                    type="date"
                    value-format="YYYY-MM-DD"
                    placeholder="选择投递日期"
                  />
                </ElFormItem>
                <ElFormItem label="联系人">
                  <ElInput v-model="editForm.contact_name" />
                </ElFormItem>
                <ElFormItem label="联系邮箱">
                  <ElInput v-model="editForm.contact_email" />
                </ElFormItem>
              </div>
              <ElFormItem label="备注">
                <ElInput v-model="editForm.notes" type="textarea" :rows="4" />
              </ElFormItem>
              <ElButton type="primary" :loading="saving" @click="saveApplication">
                保存修改
              </ElButton>
            </ElForm>
          </ElTabPane>

          <ElTabPane :label="`日程 ${relatedTasks(selected.id).length}`">
            <div class="record-list">
              <div v-for="task in relatedTasks(selected.id)" :key="task.id" class="record-row">
                <span
                  class="record-dot"
                  :style="{ borderColor: taskTypeMeta[task.task_type].color }"
                />
                <div>
                  <strong>{{ taskLabel(task) }}</strong>
                  <span>{{ formatDateTime(taskTime(task)) }} · {{ taskTypeMeta[task.task_type].label }}</span>
                </div>
                <ElTag :type="taskStatusMeta[task.status].type" effect="plain" size="small">
                  {{ taskStatusMeta[task.status].label }}
                </ElTag>
              </div>
              <div v-if="relatedTasks(selected.id).length === 0" class="drawer-empty">
                暂无关联日程
              </div>
            </div>
          </ElTabPane>

          <ElTabPane :label="`关联邮件 ${relatedEmails(selected.id).length}`">
            <div class="record-list">
              <RouterLink
                v-for="email in relatedEmails(selected.id)"
                :key="email.id"
                :to="`/mail/${email.id}`"
                class="email-record"
              >
                <div>
                  <strong>{{ email.subject }}</strong>
                  <span>{{ email.from_name || email.from_address }}</span>
                </div>
                <time>{{ formatDateTime(email.received_at) }}</time>
              </RouterLink>
              <div v-if="relatedEmails(selected.id).length === 0" class="drawer-empty">
                暂无关联邮件
              </div>
            </div>
          </ElTabPane>

          <ElTabPane :label="`面试轮次 ${interviewRounds.length}`">
            <div v-loading="loadingEvents" class="record-list">
              <div v-if="interviewRounds.length === 0 && !loadingEvents" class="drawer-empty">
                暂无面试轮次，AI 处理面试邮件或手动登记面试后将显示
              </div>
              <div
                v-for="round in [...interviewRounds].sort((a, b) => a.round_number - b.round_number)"
                :key="round.id"
                class="round-card"
              >
                <div class="round-header">
                  <span class="round-number">{{ interviewRoundLabel(round.round_number) }}</span>
                  <ElTag
                    :type="roundResultMeta[round.result]?.type ?? 'info'"
                    effect="light"
                    size="small"
                  >
                    {{ interviewResultLabel(round.result) }}
                  </ElTag>
                  <span v-if="round.source === 'EMAIL'" class="round-source">来自邮件</span>
                </div>
                <div class="round-body">
                  <div v-if="round.interview_date" class="round-detail">
                    <span>面试时间</span>
                    <strong>{{ formatDateTime(round.interview_date) }}</strong>
                  </div>
                  <div v-if="round.location" class="round-detail">
                    <span>地点</span>
                    <strong>{{ round.location }}</strong>
                  </div>
                  <button
                    type="button"
                    class="round-edit-btn"
                    @click="openRoundResult(round)"
                  >
                    编辑本轮结果
                  </button>
                </div>
              </div>
            </div>
          </ElTabPane>

          <ElTabPane :label="`时间线 ${applicationEvents.length}`">
            <div v-loading="loadingEvents" class="record-list">
              <div v-for="event in applicationEvents" :key="event.id" class="record-row">
                <span class="record-dot" />
                <div>
                  <strong>{{ eventTypeLabels[event.event_type] || '申请事件' }}</strong>
                  <span>
                    {{ applicationEventSummary(event) }}
                  </span>
                </div>
                <time>{{ formatDateTime(event.event_at || event.created_at) }}</time>
              </div>
              <div v-if="!loadingEvents && applicationEvents.length === 0" class="drawer-empty">
                暂无申请时间线事件
              </div>
            </div>
          </ElTabPane>
        </ElTabs>
      </div>
    </ElDrawer>

    <ElDialog
      v-model="resultVisible"
      title="记录面试结果"
      width="min(560px, 92vw)"
      class="result-dialog"
    >
      <template #header>
        <div class="result-dialog-heading">
          <span>记录面试结果</span>
          <small v-if="selected">{{ selected.company_name }} · {{ selected.position_name }}</small>
        </div>
      </template>
      <div v-if="selected" class="result-editor">
        <div class="result-current">
          <span>当前进度</span>
          <strong>{{ applicationStageLabel(selected) }}</strong>
          <i>选择本轮面试的最新结果</i>
        </div>
        <div class="result-options" role="radiogroup" aria-label="面试结果">
          <button
            v-for="option in interviewResultOptions"
            :key="option.value"
            type="button"
            class="result-option"
            :class="[{ active: resultForm.result === option.value }, interviewResultClass(option.value)]"
            role="radio"
            :aria-checked="resultForm.result === option.value"
            @click="resultForm.result = option.value"
          >
            <span class="option-mark" />
            <strong>{{ option.label }}</strong>
            <small>{{ option.description }}</small>
          </button>
        </div>
        <div v-if="resultForm.result === 'PASSED'" class="next-stage-preview">
          <span>保存后的下一阶段</span>
          <strong>待确认</strong>
          <small>保存后可继续登记下一轮面试，或确认进入 Offer。</small>
        </div>
        <label class="result-reason">
          <span>结果来源</span>
          <ElInput
            v-model="resultForm.reason"
            type="textarea"
            :rows="3"
            maxlength="1000"
            placeholder="例如：招聘网站显示一面通过，等待二面安排"
          />
        </label>
      </div>
      <template #footer>
        <ElButton @click="resultVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="savingResult" @click="updateInterviewResult">
          保存面试结果
        </ElButton>
      </template>
    </ElDialog>

    <ElDialog
      v-model="roundResultVisible"
      :title="`编辑${roundResultForm.roundLabel}面试结果`"
      width="min(520px, 92vw)"
      class="result-dialog"
    >
      <template #header>
        <div class="result-dialog-heading">
          <span>编辑{{ roundResultForm.roundLabel }}面试结果</span>
          <small v-if="selected">{{ selected.company_name }} · {{ selected.position_name }}</small>
        </div>
      </template>
      <div v-if="selected" class="result-editor">
        <div class="result-current">
          <span>当前轮次</span>
          <strong>{{ roundResultForm.roundLabel }}</strong>
          <i>选择本轮面试的最新结果</i>
        </div>
        <div class="result-options" role="radiogroup" aria-label="面试结果">
          <button
            v-for="option in interviewResultOptions"
            :key="option.value"
            type="button"
            class="result-option"
            :class="[
              { active: roundResultForm.result === option.value },
              interviewResultClass(option.value),
            ]"
            role="radio"
            :aria-checked="roundResultForm.result === option.value"
            @click="roundResultForm.result = option.value"
          >
            <span class="option-mark" />
            <strong>{{ option.label }}</strong>
            <small>{{ option.description }}</small>
          </button>
        </div>
        <label class="result-reason">
          <span>修改说明</span>
          <ElInput
            v-model="roundResultForm.reason"
            type="textarea"
            :rows="3"
            maxlength="1000"
            placeholder="例如：电话确认已通过本轮面试，等待下一轮安排"
          />
        </label>
      </div>
      <template #footer>
        <ElButton @click="roundResultVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="savingRoundResult" @click="updateRoundResult">
          保存面试结果
        </ElButton>
      </template>
    </ElDialog>

    <ElDialog
      v-model="nextInterviewVisible"
      :title="`登记${selected ? interviewRoundLabel(nextInterviewRound(selected.id)) : '下一轮面试'}`"
      width="min(580px, 92vw)"
    >
      <ElForm label-position="top">
        <div class="form-grid">
          <ElFormItem label="日程标题" required>
            <ElInput v-model="nextInterviewForm.title" />
          </ElFormItem>
          <ElFormItem label="面试轮次">
            <ElInput
              :model-value="selected ? interviewRoundLabel(nextInterviewRound(selected.id)) : ''"
              disabled
            />
          </ElFormItem>
          <ElFormItem label="开始时间" required>
            <ElDatePicker
              v-model="nextInterviewForm.start_at"
              type="datetime"
              value-format="YYYY-MM-DDTHH:mm"
              class="full-width"
              placeholder="选择下一轮面试时间"
            />
          </ElFormItem>
          <ElFormItem label="结束或截止时间">
            <ElDatePicker
              v-model="nextInterviewForm.deadline_at"
              type="datetime"
              value-format="YYYY-MM-DDTHH:mm"
              class="full-width"
              placeholder="可选"
            />
          </ElFormItem>
          <ElFormItem label="地点">
            <ElInput v-model="nextInterviewForm.location" />
          </ElFormItem>
          <ElFormItem label="会议链接">
            <ElInput v-model="nextInterviewForm.meeting_url" placeholder="https://..." />
          </ElFormItem>
        </div>
        <ElFormItem label="说明">
          <ElInput v-model="nextInterviewForm.description" type="textarea" :rows="2" />
        </ElFormItem>
        <ElFormItem label="安排来源" required>
          <ElInput
            v-model="nextInterviewForm.reason"
            type="textarea"
            :rows="3"
            maxlength="1000"
            placeholder="例如：招聘人员电话通知三面时间"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="nextInterviewVisible = false">取消</ElButton>
        <ElButton
          type="primary"
          :loading="schedulingNextInterview"
          @click="scheduleNextInterview"
        >
          保存下一轮日程
        </ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="offerVisible" title="记录 Offer 结果" width="min(520px, 92vw)">
      <ElForm label-position="top">
        <ElFormItem label="结果" required>
          <ElSelect v-model="offerForm.result" class="full-width">
            <ElOption label="待确认 Offer" value="PENDING" />
            <ElOption label="已接受 Offer" value="ACCEPTED" />
            <ElOption label="已谢绝 Offer" value="DECLINED" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="结果来源" required>
          <ElInput
            v-model="offerForm.reason"
            type="textarea"
            :rows="3"
            maxlength="1000"
            placeholder="例如：电话确认已接受，或招聘网站中选择谢绝 Offer"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="offerVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="savingOffer" @click="updateOfferResult">
          保存 Offer 结果
        </ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="reopenVisible" title="重新打开申请" width="min(520px, 92vw)">
      <ElForm label-position="top">
        <ElFormItem label="恢复到阶段" required>
          <ElSelect v-model="reopenForm.target_stage" class="full-width" disabled>
            <ElOption
              v-for="(label, value) in stageMeta"
              :key="value"
              :label="label.label"
              :value="value"
            />
          </ElSelect>
          <span class="quiet" style="font-size:11px;margin-top:4px;display:block">
            重新打开将恢复到关闭前的阶段，历史面试结果和邮件关联不受影响
          </span>
        </ElFormItem>
        <ElFormItem label="重新打开原因" required>
          <ElInput
            v-model="reopenForm.reason"
            type="textarea"
            :rows="3"
            maxlength="1000"
            placeholder="例如：误操作关闭，实际流程仍在继续"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="reopenVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="reopening" @click="reopenApplication">
          确认重新打开
        </ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="stageVisible" title="更新申请阶段" width="min(460px, 92vw)">
      <ElForm label-position="top">
        <ElFormItem label="目标阶段" required>
          <ElSelect v-model="stageForm.proposed_stage" placeholder="请选择目标阶段" class="full-width">
            <ElOption
              v-for="stage in availableStages"
              :key="stage"
              :label="stageLabel(stage)"
              :value="stage"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="变更说明" required>
          <ElInput
            v-model="stageForm.reason"
            type="textarea"
            :rows="3"
            maxlength="1000"
            show-word-limit
            placeholder="例如：招聘网站显示已进入二面，或电话通知未通过"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="stageVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="transitioningStage" @click="transitionStage">
          更新阶段
        </ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="createVisible" title="新建求职申请" width="min(560px, 92vw)">
      <ElForm ref="createFormRef" :model="createForm" :rules="rules" label-position="top">
        <div class="form-grid">
          <ElFormItem label="公司名称" prop="company_name">
            <ElInput v-model="createForm.company_name" placeholder="例如：字节跳动" />
          </ElFormItem>
          <ElFormItem label="投递岗位" prop="position_name">
            <ElInput v-model="createForm.position_name" placeholder="例如：后端开发工程师" />
          </ElFormItem>
          <ElFormItem label="所在地">
            <ElInput v-model="createForm.location" />
          </ElFormItem>
          <ElFormItem label="投递时间">
            <ElDatePicker
              v-model="createForm.applied_at"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择投递日期"
            />
          </ElFormItem>
          <ElFormItem label="联系人">
            <ElInput v-model="createForm.contact_name" />
          </ElFormItem>
          <ElFormItem label="联系邮箱">
            <ElInput v-model="createForm.contact_email" />
          </ElFormItem>
        </div>
        <ElFormItem label="备注">
          <ElInput v-model="createForm.notes" type="textarea" :rows="3" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="createVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="saving" @click="createApplication">创建申请</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.applications-page {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
}

.progress-tabs {
  display: flex;
  padding: 3px;
  background: #eaedf0;
  border-radius: 7px;
}

.progress-tabs button {
  padding: 6px 13px;
  color: var(--jm-text-secondary);
  font-size: 13px;
  background: transparent;
  border: 0;
  border-radius: 5px;
  cursor: pointer;
}

.progress-tabs button.active {
  color: var(--jm-text);
  font-weight: 500;
  background: #fff;
  box-shadow: 0 1px 2px rgb(31 35 41 / 8%);
}

.result-count {
  color: var(--jm-text-tertiary);
  font-size: 12px;
}

.search-input {
  width: 220px;
}

.stage-select {
  width: 130px;
}

.full-width {
  width: 100%;
}

.progress-table {
  min-height: 0;
  overflow: hidden;
}

.progress-table :deep(.clickable-row) {
  cursor: pointer;
}

.company-name {
  font-weight: 500;
}

.result-pill {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  padding: 5px 9px;
  color: #5f6b7a;
  font: inherit;
  font-size: 12px;
  background: #f5f7fa;
  border: 1px solid transparent;
  border-radius: 999px;
  cursor: pointer;
  transition: border-color 0.16s ease, background 0.16s ease;
}

.result-pill > span {
  width: 6px;
  height: 6px;
  background: currentcolor;
  border-radius: 50%;
}

.result-pill.is-passed {
  color: #16835f;
  background: #ecf8f3;
}

.result-pill.is-failed {
  color: #c04444;
  background: #fff1f0;
}

.result-pill.is-pending {
  color: #9a6818;
  background: #fff7e6;
}

.result-pill:hover,
.result-pill:focus-visible {
  border-color: currentcolor;
  outline: none;
}

.next-task {
  display: flex;
  min-width: 0;
  gap: 8px;
  align-items: center;
}

.task-dot {
  width: 7px;
  height: 7px;
  flex: 0 0 7px;
  border-radius: 50%;
}

.next-task > div {
  display: grid;
  min-width: 0;
}

.next-task strong,
.next-task span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.next-task strong {
  font-size: 12px;
  font-weight: 500;
}

.next-task span {
  color: var(--jm-text-tertiary);
  font-size: 11px;
}

.waiting-next {
  color: #9a6818;
  font-size: 12px;
}

.table-empty {
  padding: 50px 0;
}

.application-drawer {
  padding: 0 20px 24px;
}

.drawer-stage {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 0;
  border-bottom: 1px solid var(--jm-border-light);
}

.drawer-stage .stage-identity {
  display: flex;
  gap: 9px;
  align-items: center;
}

.stage-identity > span {
  color: var(--jm-text-secondary);
  font-size: 12px;
}

.stage-identity > strong {
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -0.02em;
}

.drawer-stage p {
  margin: 0;
  margin-left: auto;
  color: var(--jm-text-tertiary);
  font-size: 11px;
  text-align: right;
  white-space: nowrap;
}

.next-step-card {
  display: grid;
  gap: 14px;
  margin: 16px 0 8px;
  padding: 16px;
  background: #fff8e8;
  border: 1px solid #f2d99b;
  border-radius: 10px;
}

.next-step-card > div:first-child {
  display: grid;
  gap: 5px;
}

.next-step-card strong {
  color: #6f4d0f;
  font-size: 14px;
}

.next-step-card span {
  color: #7c6a48;
  font-size: 12px;
  line-height: 1.6;
}

.next-step-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.result-dialog-heading {
  display: grid;
  gap: 5px;
}

.result-dialog-heading > span {
  color: #20242b;
  font-size: 19px;
  font-weight: 600;
}

.result-dialog-heading small {
  color: var(--jm-text-tertiary);
  font-size: 12px;
}

.result-editor {
  display: grid;
  gap: 20px;
}

.result-current {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 12px;
  align-items: baseline;
  padding: 14px 16px;
  background: #f6f8fb;
  border-left: 3px solid var(--jm-primary);
  border-radius: 4px 10px 10px 4px;
}

.result-current span,
.result-current i {
  color: var(--jm-text-tertiary);
  font-size: 12px;
  font-style: normal;
}

.result-current strong {
  color: #1e2735;
  font-size: 16px;
}

.result-current i {
  grid-column: 2;
}

.result-options {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.next-stage-preview {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 3px 12px;
  align-items: baseline;
  padding: 12px 14px;
  background: #fff8e8;
  border-left: 3px solid #d99a2b;
  border-radius: 4px 9px 9px 4px;
}

.next-stage-preview span,
.next-stage-preview small {
  color: #806b43;
  font-size: 12px;
}

.next-stage-preview strong {
  color: #6f4d0f;
}

.next-stage-preview small {
  grid-column: 2;
}

.result-option {
  display: grid;
  grid-template-columns: 12px 1fr;
  gap: 5px 8px;
  min-height: 92px;
  padding: 14px;
  color: #45505f;
  text-align: left;
  background: #fff;
  border: 1px solid #dfe3e9;
  border-radius: 10px;
  cursor: pointer;
  transition: transform 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
}

.result-option:hover {
  transform: translateY(-1px);
  border-color: #aeb8c6;
  box-shadow: 0 5px 16px rgb(31 42 55 / 7%);
}

.result-option.active {
  border-color: currentcolor;
  box-shadow: 0 0 0 2px color-mix(in srgb, currentcolor 13%, transparent);
}

.result-option.is-passed { color: #16835f; }
.result-option.is-failed { color: #c04444; }
.result-option.is-pending { color: #9a6818; }

.option-mark {
  width: 10px;
  height: 10px;
  margin-top: 3px;
  border: 2px solid currentcolor;
  border-radius: 50%;
}

.result-option.active .option-mark {
  background: currentcolor;
  box-shadow: inset 0 0 0 2px #fff;
}

.result-option strong {
  color: #28313e;
  font-size: 14px;
}

.result-option small {
  grid-column: 2;
  color: var(--jm-text-tertiary);
  font-size: 11px;
  line-height: 1.5;
}

.result-reason {
  display: grid;
  gap: 8px;
}

.result-reason > span {
  color: #394353;
  font-size: 13px;
  font-weight: 500;
}

.drawer-form {
  padding-top: 10px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 14px;
}

.form-grid :deep(.el-date-editor) {
  width: 100%;
}

.record-list {
  display: grid;
  padding-top: 8px;
}

.record-row {
  display: grid;
  grid-template-columns: 14px minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  padding: 13px 2px;
  border-bottom: 1px solid var(--jm-border-light);
}

.record-dot {
  width: 10px;
  height: 10px;
  border: 2px solid;
  border-radius: 50%;
}

.record-row > div {
  display: grid;
  gap: 3px;
}

.record-row strong,
.email-record strong {
  font-size: 13px;
  font-weight: 500;
}

.record-row span,
.email-record span,
.email-record time {
  color: var(--jm-text-tertiary);
  font-size: 11px;
}

.email-record {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 13px 2px;
  border-bottom: 1px solid var(--jm-border-light);
}

.email-record > div {
  display: grid;
  gap: 3px;
}

.email-record:hover strong {
  color: var(--jm-primary);
}

.drawer-empty {
  padding: 60px 0;
  color: var(--jm-text-tertiary);
  text-align: center;
}

@media (max-width: 850px) {
  .page-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .toolbar-group:last-child,
  .search-input {
    width: 100%;
  }
}

.round-card {
  display: grid;
  gap: 10px;
  padding: 14px 2px;
  border-bottom: 1px solid var(--jm-border-light);
}

.round-header {
  display: flex;
  gap: 8px;
  align-items: center;
}

.round-number {
  font-size: 14px;
  font-weight: 600;
  color: #1e2735;
  min-width: 40px;
}

.round-source {
  margin-left: auto;
  color: var(--jm-text-tertiary);
  font-size: 11px;
  background: #f5f6f7;
  padding: 1px 8px;
  border-radius: 4px;
}

.round-body {
  display: grid;
  gap: 6px;
  padding-left: 0;
}

.round-detail {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 8px;
  align-items: baseline;
}

.round-detail span {
  color: var(--jm-text-tertiary);
  font-size: 11px;
}

.round-detail strong {
  font-size: 12px;
  font-weight: 500;
}

.round-edit-btn {
  justify-self: start;
  margin-top: 4px;
  padding: 3px 10px;
  font-size: 11px;
  color: var(--jm-primary);
  background: transparent;
  border: 1px solid var(--jm-border);
  border-radius: 4px;
  cursor: pointer;
}

.round-edit-btn:hover {
  background: #f0f5ff;
}

@media (max-width: 560px) {
  .drawer-stage {
    align-items: flex-start;
    flex-direction: column;
    gap: 10px;
  }

  .drawer-stage p {
    margin-left: 0;
    text-align: left;
    white-space: normal;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .result-options {
    grid-template-columns: 1fr;
  }

  .result-option {
    min-height: 0;
  }
}
</style>
