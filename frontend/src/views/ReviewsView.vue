<script setup lang="ts">
import { Refresh, Search, Warning } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { emailApi, reviewApi } from '@/api'
import { getApiErrorMessage } from '@/api/http'
import {
  reviewActionMeta,
  reviewStatusMeta,
  riskMeta,
} from '@/utils/dictionaries'
import { formatDateTime } from '@/utils/format'
import type { EmailListItem, ReviewTask } from '@/types/api'

type ReviewFilter = 'pending' | 'processed'

const route = useRoute()
const router = useRouter()

const tasks = ref<ReviewTask[]>([])
const emails = ref<EmailListItem[]>([])
const filter = ref<ReviewFilter>('pending')
const keyword = ref('')
const loading = ref(false)
const deciding = ref(false)
const drawerVisible = ref(false)
const selected = ref<ReviewTask | null>(null)
const payloadText = ref('')
const decisionReason = ref('')

const filteredTasks = computed(() => {
  const normalized = keyword.value.trim().toLowerCase()
  return tasks.value.filter((task) => {
    if (filter.value === 'pending' && task.status !== 'PENDING') return false
    if (filter.value === 'processed' && task.status === 'PENDING') return false
    if (!normalized) return true
    return [
      reviewActionMeta[task.action_type],
      sourceEmail(task.source_email_id)?.subject,
      task.id,
    ]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(normalized))
  })
})

function sourceEmail(id: number | null): EmailListItem | undefined {
  return id ? emails.value.find((email) => email.id === id) : undefined
}

function actionLabel(task: ReviewTask): string {
  return reviewActionMeta[task.action_type]
}

function riskLabel(task: ReviewTask): string {
  return riskMeta[task.risk_level].label
}

function riskType(task: ReviewTask) {
  return riskMeta[task.risk_level].type
}

function statusLabel(task: ReviewTask): string {
  return reviewStatusMeta[task.status].label
}

function statusType(task: ReviewTask) {
  return reviewStatusMeta[task.status].type
}

async function loadData() {
  loading.value = true
  try {
    const [taskRows, emailRows] = await Promise.all([reviewApi.list(), emailApi.list()])
    tasks.value = taskRows.sort((a, b) => b.created_at.localeCompare(a.created_at))
    emails.value = emailRows

    const taskId = String(route.params.taskId ?? '')
    if (taskId) {
      const task = taskRows.find((item) => item.id === taskId) ?? (await reviewApi.detail(taskId))
      openTask(task, false)
    }
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function openTask(task: ReviewTask, updateRoute = true) {
  selected.value = task
  payloadText.value = JSON.stringify(task.reviewed_payload ?? task.proposed_payload, null, 2)
  decisionReason.value = task.decision_reason ?? ''
  drawerVisible.value = true
  if (updateRoute) void router.replace(`/reviews/${task.id}`)
}

function closeDrawer() {
  if (route.params.taskId) void router.replace('/reviews')
}

function parsePayload(): Record<string, unknown> | null {
  try {
    const value: unknown = JSON.parse(payloadText.value)
    if (!value || Array.isArray(value) || typeof value !== 'object') {
      ElMessage.warning('确认内容必须是 JSON 对象')
      return null
    }
    return value as Record<string, unknown>
  } catch {
    ElMessage.warning('确认内容不是有效的 JSON')
    return null
  }
}

async function approve() {
  if (!selected.value || selected.value.status !== 'PENDING') return
  const payload = parsePayload()
  if (!payload) return

  if (selected.value.action_type === 'SEND_REPLY') {
    try {
      await ElMessageBox.confirm(
        '批准后系统将通过 SMTP 真实发送这封邮件，且同一幂等键只执行一次。',
        '确认发送回复',
        {
          confirmButtonText: '确认并发送',
          cancelButtonText: '返回检查',
          type: 'warning',
        },
      )
    } catch {
      return
    }
  }

  await decide(true, payload)
}

async function reject() {
  if (!selected.value || selected.value.status !== 'PENDING') return
  if (!decisionReason.value.trim()) {
    ElMessage.warning('请填写拒绝原因，便于后续追踪')
    return
  }
  await decide(false, null)
}

async function decide(approveDecision: boolean, payload: Record<string, unknown> | null) {
  if (!selected.value) return
  deciding.value = true
  try {
    const response = await reviewApi.decide(selected.value.id, {
      version: selected.value.version,
      approve: approveDecision,
      reviewed_payload: payload,
      reason: decisionReason.value.trim() || null,
    })

    ElMessage.success(
      approveDecision
        ? selected.value.action_type === 'SEND_REPLY'
          ? '回复已确认发送'
          : '审核已批准'
        : '审核已拒绝',
    )

    if (response.follow_up_review_task) {
      ElMessage.info('工作流已进入下一项审核')
      await loadData()
      openTask(response.follow_up_review_task)
    } else {
      drawerVisible.value = false
      await router.replace('/reviews')
      await loadData()
    }
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    deciding.value = false
  }
}

function payloadSummary(task: ReviewTask): string {
  const payload = task.proposed_payload
  const values = [
    payload.company_name,
    payload.position_name,
    payload.title,
    payload.subject,
    payload.proposed_stage,
    payload.application_id,
  ].filter((value) => value !== null && value !== undefined && String(value).trim())
  return values.length ? values.slice(0, 2).join(' · ') : '查看建议内容'
}

function fieldLabel(key: string): string {
  const labels: Record<string, string> = {
    company_name: '公司',
    position_name: '岗位',
    application_id: '申请记录',
    proposed_stage: '建议阶段',
    current_stage: '当前阶段',
    title: '标题',
    subject: '邮件主题',
    to_recipients: '收件人',
    start_at: '开始时间',
    deadline_at: '截止时间',
    location: '地点',
    meeting_url: '会议链接',
    generated_body: '回复正文',
    reviewed_body: '回复正文',
  }
  return labels[key] ?? key
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

watch(
  () => route.params.taskId,
  (value) => {
    const id = String(value ?? '')
    if (!id) return
    const task = tasks.value.find((item) => item.id === id)
    if (task && task.id !== selected.value?.id) openTask(task, false)
  },
)

onMounted(loadData)
</script>

<template>
  <div class="page-shell reviews-page">
    <div class="page-toolbar">
      <div class="toolbar-group">
        <div class="review-tabs">
          <button
            type="button"
            :class="{ active: filter === 'pending' }"
            @click="filter = 'pending'"
          >
            待审核
            <span>{{ tasks.filter((task) => task.status === 'PENDING').length }}</span>
          </button>
          <button
            type="button"
            :class="{ active: filter === 'processed' }"
            @click="filter = 'processed'"
          >
            已处理
          </button>
        </div>
      </div>
      <div class="toolbar-group">
        <ElInput
          v-model="keyword"
          class="review-search"
          clearable
          :prefix-icon="Search"
          placeholder="搜索审核任务"
        />
        <ElButton :icon="Refresh" @click="loadData">刷新</ElButton>
      </div>
    </div>

    <section class="surface review-table">
      <ElTable
        v-loading="loading"
        :data="filteredTasks"
        height="100%"
        row-class-name="review-row"
        @row-click="openTask"
      >
        <ElTableColumn label="审核事项" min-width="160">
          <template #default="{ row }">
            <div class="action-cell">
              <span class="ai-marker" />
              <strong>{{ actionLabel(row) }}</strong>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn label="来源邮件" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            {{ sourceEmail(row.source_email_id)?.subject || '系统任务' }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="建议内容" min-width="210" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="muted">{{ payloadSummary(row) }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="风险" width="100">
          <template #default="{ row }">
            <ElTag :type="riskType(row)" effect="plain">
              {{ riskLabel(row) }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="状态" width="104">
          <template #default="{ row }">
            <ElTag :type="statusType(row)" effect="light">
              {{ statusLabel(row) }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="创建时间" width="150">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </ElTableColumn>
        <template #empty>
          <div class="review-empty">
            <p>{{ filter === 'pending' ? '没有待审核事项' : '还没有已处理记录' }}</p>
            <span v-if="filter === 'pending'">新的智能处理建议会出现在这里</span>
          </div>
        </template>
      </ElTable>
    </section>

    <ElDrawer
      v-model="drawerVisible"
      size="min(600px, 94vw)"
      :before-close="(done: () => void) => { closeDrawer(); done() }"
      :title="selected ? reviewActionMeta[selected.action_type] : '审核详情'"
    >
      <div v-if="selected" class="review-drawer">
        <div class="risk-banner" :class="`risk-${selected.risk_level.toLowerCase()}`">
          <ElIcon><Warning /></ElIcon>
          <div>
            <strong>{{ riskMeta[selected.risk_level].label }}</strong>
            <span>
              {{
                selected.action_type === 'SEND_REPLY'
                  ? '批准后会执行真实邮件发送，请检查收件人和正文。'
                  : '批准后系统才会写入对应业务状态。'
              }}
            </span>
          </div>
        </div>

        <section class="review-section">
          <h3>来源</h3>
          <RouterLink
            v-if="sourceEmail(selected.source_email_id)"
            :to="`/mail/${selected.source_email_id}`"
            class="source-card"
          >
            <div>
              <strong>{{ sourceEmail(selected.source_email_id)?.subject }}</strong>
              <span>{{ sourceEmail(selected.source_email_id)?.from_name || sourceEmail(selected.source_email_id)?.from_address }}</span>
            </div>
            <span>查看邮件</span>
          </RouterLink>
          <div v-else class="source-card">
            <span>该任务没有来源邮件</span>
          </div>
        </section>

        <section class="review-section">
          <h3>建议内容</h3>
          <dl class="payload-list">
            <div v-for="(value, key) in selected.proposed_payload" :key="key">
              <dt>{{ fieldLabel(String(key)) }}</dt>
              <dd>{{ displayValue(value) }}</dd>
            </div>
          </dl>
        </section>

        <section v-if="selected.status === 'PENDING'" class="review-section">
          <h3>确认内容</h3>
          <p class="section-hint">可以在批准前修改结构化内容；必须保持有效的 JSON 对象。</p>
          <ElInput
            v-model="payloadText"
            type="textarea"
            :rows="12"
            resize="vertical"
            class="payload-editor"
          />
          <label class="reason-label" for="decision-reason">审核说明</label>
          <ElInput
            id="decision-reason"
            v-model="decisionReason"
            type="textarea"
            :rows="2"
            placeholder="拒绝时请填写原因；批准时可选"
          />
        </section>

        <section v-else class="review-section">
          <h3>处理结果</h3>
          <dl class="result-list">
            <div>
              <dt>状态</dt>
              <dd>{{ reviewStatusMeta[selected.status].label }}</dd>
            </div>
            <div>
              <dt>处理时间</dt>
              <dd>{{ formatDateTime(selected.reviewed_at) }}</dd>
            </div>
            <div>
              <dt>处理说明</dt>
              <dd>{{ selected.decision_reason || '—' }}</dd>
            </div>
          </dl>
        </section>
      </div>

      <template v-if="selected?.status === 'PENDING'" #footer>
        <div class="drawer-actions">
          <ElButton :disabled="deciding" @click="reject">拒绝</ElButton>
          <ElButton type="primary" :loading="deciding" @click="approve">
            {{ selected.action_type === 'SEND_REPLY' ? '确认并发送' : '批准' }}
          </ElButton>
        </div>
      </template>
    </ElDrawer>
  </div>
</template>

<style scoped>
.reviews-page {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
}

.review-tabs {
  display: flex;
  gap: 22px;
}

.review-tabs button {
  display: flex;
  height: 38px;
  gap: 7px;
  align-items: center;
  padding: 0 2px;
  color: var(--jm-text-secondary);
  background: transparent;
  border: 0;
  border-bottom: 2px solid transparent;
  cursor: pointer;
}

.review-tabs button.active {
  color: var(--jm-text);
  font-weight: 600;
  border-bottom-color: var(--jm-primary);
}

.review-tabs span {
  min-width: 19px;
  height: 19px;
  padding: 0 5px;
  color: #9a5c12;
  font-size: 11px;
  line-height: 19px;
  background: #fff1d6;
  border-radius: 10px;
}

.review-search {
  width: 240px;
}

.review-table {
  min-height: 0;
  overflow: hidden;
}

.review-table :deep(.review-row) {
  cursor: pointer;
}

.action-cell {
  display: flex;
  gap: 8px;
  align-items: center;
}

.action-cell strong {
  font-weight: 500;
}

.ai-marker {
  width: 7px;
  height: 7px;
  background: #7b61d1;
  border-radius: 50%;
}

.review-empty {
  display: grid;
  gap: 4px;
  padding: 70px 0;
}

.review-empty p {
  margin: 0;
  color: var(--jm-text-secondary);
}

.review-empty span {
  color: var(--jm-text-tertiary);
  font-size: 12px;
}

.review-drawer {
  padding: 18px 20px 90px;
}

.risk-banner {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 12px 14px;
  border-radius: 7px;
}

.risk-banner > div {
  display: grid;
  gap: 3px;
}

.risk-banner strong {
  font-size: 13px;
}

.risk-banner span {
  font-size: 12px;
}

.risk-low {
  color: #416070;
  background: #f0f5f7;
}

.risk-medium {
  color: #895814;
  background: #fff6e3;
}

.risk-high {
  color: #a33832;
  background: #fff0ef;
}

.review-section {
  margin-top: 24px;
}

.review-section h3 {
  margin: 0 0 10px;
  font-size: 14px;
}

.section-hint {
  margin: -4px 0 10px;
  color: var(--jm-text-tertiary);
  font-size: 11px;
}

.source-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border: 1px solid var(--jm-border-light);
  border-radius: 7px;
}

.source-card > div {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.source-card strong {
  overflow: hidden;
  font-size: 13px;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-card span {
  color: var(--jm-text-tertiary);
  font-size: 11px;
}

.source-card > span:last-child {
  flex: 0 0 auto;
  margin-left: 12px;
  color: var(--jm-primary);
}

.payload-list,
.result-list {
  margin: 0;
  border: 1px solid var(--jm-border-light);
  border-radius: 7px;
  overflow: hidden;
}

.payload-list div,
.result-list div {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  border-bottom: 1px solid var(--jm-border-light);
}

.payload-list div:last-child,
.result-list div:last-child {
  border-bottom: 0;
}

.payload-list dt,
.payload-list dd,
.result-list dt,
.result-list dd {
  margin: 0;
  padding: 10px 12px;
  white-space: pre-wrap;
  word-break: break-word;
}

.payload-list dt,
.result-list dt {
  color: var(--jm-text-secondary);
  font-size: 12px;
  background: #f8f9fa;
  border-right: 1px solid var(--jm-border-light);
}

.payload-list dd,
.result-list dd {
  font-size: 12px;
}

.payload-editor :deep(textarea) {
  font-family: "Cascadia Code", "SFMono-Regular", Consolas, monospace;
  font-size: 12px;
  line-height: 1.55;
}

.reason-label {
  display: block;
  margin: 16px 0 7px;
  font-size: 13px;
  font-weight: 500;
}

.drawer-actions {
  display: flex;
  justify-content: flex-end;
  padding: 10px 0;
}

@media (max-width: 700px) {
  .page-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .review-search {
    width: 100%;
  }

  .toolbar-group:last-child {
    width: 100%;
  }
}
</style>
