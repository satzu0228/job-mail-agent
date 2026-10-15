<script setup lang="ts">
import {
  ArrowRight,
  VideoCamera,
} from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { dashboardApi, taskApi } from '@/api'
import { getApiErrorMessage } from '@/api/http'
import { usePollingStore } from '@/stores/polling'
import {
  reviewActionMeta,
  riskMeta,
  taskStatusMeta,
} from '@/utils/dictionaries'
import { formatRelativeDate, taskTime } from '@/utils/format'
import type { DashboardData, ReviewTask, Task } from '@/types/api'

// ------------------------------------------------------------------
// Section urgency colours — consistent with CalendarView type-line pattern
// ------------------------------------------------------------------
const URGENCY = {
  deadline: '#d54941',   // red
  interview: '#3370ff',  // blue
  review: '#d27b17',     // amber
} as const

const router = useRouter()
const pollingStore = usePollingStore()
let unsubscribePolling: (() => void) | undefined

const data = ref<DashboardData | null>(null)
const loading = ref(true)
const error = ref('')

// ------------------------------------------------------------------
// Derived
// ------------------------------------------------------------------

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 12) return '早上好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const isEmpty = computed(() => {
  if (!data.value) return true
  const d = data.value
  return (
    d.upcoming_interviews.length === 0
    && d.urgent_deadlines.length === 0
    && d.pending_reviews.length === 0
  )
})

// ------------------------------------------------------------------
// Data loading
// ------------------------------------------------------------------

async function load() {
  try {
    data.value = await dashboardApi.get()
    error.value = ''
  } catch (err) {
    error.value = getApiErrorMessage(err)
  } finally {
    loading.value = false
  }
}

async function markTaskDone(task: Task) {
  try {
    const updated = await taskApi.update(task.id, {
      version: task.version,
      status: 'COMPLETED',
    })
    if (data.value) {
      const replaceIn = (list: Task[]) => {
        const idx = list.findIndex((t) => t.id === task.id)
        if (idx >= 0) list[idx] = updated
      }
      replaceIn(data.value.upcoming_interviews)
      replaceIn(data.value.urgent_deadlines)
    }
    ElMessage.success('已标记为完成')
  } catch (err) {
    ElMessage.error(getApiErrorMessage(err))
  }
}

// ------------------------------------------------------------------
// Navigation
// ------------------------------------------------------------------

function goToTask(task: Task) {
  void router.push('/calendar')
}

function goToReview(review: ReviewTask) {
  void router.push(`/reviews/${review.id}`)
}

// ------------------------------------------------------------------
// Helpers
// ------------------------------------------------------------------

function urgencyColor(task: Task): string {
  if (task.task_type === 'INTERVIEW') return URGENCY.interview
  if (task.task_type === 'DEADLINE') return URGENCY.deadline
  if (task.task_type === 'MATERIAL') return URGENCY.deadline
  if (task.task_type === 'ASSESSMENT') return URGENCY.deadline
  return '#8f959e'
}

function timeLabel(task: Task): string {
  const time = taskTime(task)
  if (!time) return '时间待确认'
  const d = dayjs(time)
  const now = dayjs()
  if (d.isSame(now, 'day')) return `今天 ${d.format('HH:mm')}`
  if (d.isSame(now.add(1, 'day'), 'day')) return `明天 ${d.format('HH:mm')}`
  return d.format('MM月DD日 HH:mm')
}

function deadlineLabel(task: Task): string {
  const time = task.deadline_at ?? task.start_at
  if (!time) return '时间待确认'
  const d = dayjs(time)
  const now = dayjs()
  const hours = d.diff(now, 'hour')
  if (hours < 1) {
    const mins = d.diff(now, 'minute')
    return `${Math.max(mins, 1)} 分钟后截止`
  }
  if (hours < 24) return `${hours} 小时后截止`
  return d.format('MM月DD日 HH:mm 截止')
}

function applicationLabel(task: Task): string {
  // We don't have full application info here, just the task context.
  // Show location or meeting_url hint instead.
  if (task.location) return task.location
  if (task.meeting_url) return '线上会议'
  return ''
}

function applicationForReview(review: ReviewTask): string {
  const payload = review.proposed_payload as Record<string, unknown> | null
  if (!payload) return ''
  const company = typeof payload.company_name === 'string' ? payload.company_name : ''
  const position = typeof payload.position_name === 'string' ? payload.position_name : ''
  if (company && position) return `${company} · ${position}`
  return company || position || ''
}

// ------------------------------------------------------------------
// Lifecycle
// ------------------------------------------------------------------

onMounted(() => {
  void load()
  unsubscribePolling = pollingStore.subscribe('dashboard', load)
})

onBeforeUnmount(() => {
  unsubscribePolling?.()
})
</script>

<template>
  <div class="page-shell dashboard-page">
    <!-- Greeting -->
    <div class="greeting-row">
      <h2 class="greeting">{{ greeting }}</h2>
    </div>

    <!-- Funnel Stats -->
    <div v-if="data" class="stat-strip surface">
      <div class="stat-pill">
        <span class="stat-number">{{ data.stats.applied }}</span>
        <span class="stat-label">总投递</span>
      </div>
      <div class="stat-pill">
        <span class="stat-number">{{ data.stats.in_progress }}</span>
        <span class="stat-label">进行中</span>
      </div>
      <div class="stat-pill">
        <span class="stat-number stat-offer">{{ data.stats.offered }}</span>
        <span class="stat-label">已 Offer</span>
      </div>
      <div class="stat-pill">
        <span class="stat-number muted">{{ data.stats.rejected }}</span>
        <span class="stat-label">已结束</span>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="dashboard-loading">
      <ElSkeleton :rows="4" animated />
      <ElSkeleton :rows="3" animated style="margin-top: 20px" />
      <ElSkeleton :rows="2" animated style="margin-top: 20px" />
    </div>

    <!-- Error -->
    <div v-else-if="error" class="empty-state">
      <div>
        <p>{{ error }}</p>
        <ElButton type="primary" text @click="load">重试</ElButton>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else-if="isEmpty" class="empty-state dashboard-empty">
      <div>
        <p class="empty-title">🎉 暂无需要你处理的任务</p>
        <span class="quiet">系统已自动处理最近的邮件，一切正常</span>
      </div>
    </div>

    <!-- Content -->
    <template v-else-if="data">
      <!-- Urgent Deadlines -->
      <section v-if="data.urgent_deadlines.length" class="dashboard-section">
        <div class="section-header">
          <div class="section-badge" :style="{ background: URGENCY.deadline }" />
          <h3 class="section-title">24h 内截止</h3>
          <span class="section-count">{{ data.urgent_deadlines.length }}</span>
        </div>
        <div class="section-body surface">
          <button
            v-for="task in data.urgent_deadlines"
            :key="task.id"
            type="button"
            class="dashboard-row"
            @click="goToTask(task)"
          >
            <span
              class="row-urgency"
              :style="{ background: urgencyColor(task) }"
            />
            <div class="row-main">
              <strong class="row-title">{{ task.title }}</strong>
              <span v-if="applicationLabel(task)" class="row-sub quiet">{{ applicationLabel(task) }}</span>
            </div>
            <div class="row-meta">
              <span class="row-time urgent">{{ deadlineLabel(task) }}</span>
              <ElTag
                :type="taskStatusMeta[task.status].type"
                effect="plain"
                size="small"
              >
                {{ taskStatusMeta[task.status].label }}
              </ElTag>
            </div>
            <ElIcon class="row-chevron quiet"><ArrowRight /></ElIcon>
          </button>
        </div>
      </section>

      <!-- Upcoming Interviews -->
      <section v-if="data.upcoming_interviews.length" class="dashboard-section">
        <div class="section-header">
          <div class="section-badge" :style="{ background: URGENCY.interview }" />
          <h3 class="section-title">今明面试</h3>
          <span class="section-count">{{ data.upcoming_interviews.length }}</span>
        </div>
        <div class="section-body surface">
          <button
            v-for="task in data.upcoming_interviews"
            :key="task.id"
            type="button"
            class="dashboard-row"
            @click="goToTask(task)"
          >
            <span
              class="row-urgency"
              :style="{ background: urgencyColor(task) }"
            />
            <div class="row-main">
              <strong class="row-title">{{ task.title }}</strong>
              <span v-if="applicationLabel(task)" class="row-sub quiet">
                <ElIcon v-if="task.meeting_url" :size="13"><VideoCamera /></ElIcon>
                {{ applicationLabel(task) }}
              </span>
            </div>
            <div class="row-meta">
              <span class="row-time">{{ timeLabel(task) }}</span>
              <ElTag
                :type="taskStatusMeta[task.status].type"
                effect="plain"
                size="small"
              >
                {{ taskStatusMeta[task.status].label }}
              </ElTag>
            </div>
            <ElIcon class="row-chevron quiet"><ArrowRight /></ElIcon>
          </button>
        </div>
      </section>

      <!-- Pending Reviews -->
      <section v-if="data.pending_reviews.length" class="dashboard-section">
        <div class="section-header">
          <div class="section-badge" :style="{ background: URGENCY.review }" />
          <h3 class="section-title">待审核</h3>
          <span class="section-count">{{ data.pending_reviews.length }}</span>
        </div>
        <div class="section-body surface">
          <button
            v-for="review in data.pending_reviews"
            :key="review.id"
            type="button"
            class="dashboard-row"
            @click="goToReview(review)"
          >
            <span
              class="row-urgency"
              :style="{ background: URGENCY.review }"
            />
            <div class="row-main">
              <strong class="row-title">{{ reviewActionMeta[review.action_type] }}</strong>
              <span v-if="applicationForReview(review)" class="row-sub quiet">
                {{ applicationForReview(review) }}
              </span>
            </div>
            <div class="row-meta">
              <ElTag
                v-if="review.risk_level === 'HIGH'"
                :type="riskMeta.HIGH.type"
                effect="plain"
                size="small"
              >
                高风险
              </ElTag>
              <span class="row-time quiet">{{ formatRelativeDate(review.created_at) }}</span>
            </div>
            <ElIcon class="row-chevron quiet"><ArrowRight /></ElIcon>
          </button>
        </div>
      </section>

    </template>
  </div>
</template>

<style scoped>
.dashboard-page {
  max-width: 980px;
  margin: 0 auto;
}

/* Greeting */
.greeting-row {
  margin-bottom: 20px;
}

.greeting {
  margin: 0;
  font-size: 22px;
  font-weight: 650;
  letter-spacing: -0.01em;
}

/* Stat Strip */
.stat-strip {
  display: flex;
  gap: 0;
  padding: 14px 8px;
  margin-bottom: 24px;
}

.stat-pill {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 2px;
  padding: 10px 16px;
  text-align: center;
  border-right: 1px solid var(--jm-border-light);
}

.stat-pill:last-child {
  border-right: 0;
}

.stat-number {
  font-size: 22px;
  font-weight: 650;
  color: var(--jm-text);
  line-height: 1.2;
}

.stat-number.stat-offer {
  color: var(--jm-success);
}

.stat-label {
  font-size: 11px;
  color: var(--jm-text-tertiary);
}

/* Sections */
.dashboard-section {
  margin-bottom: 20px;
}

.section-header {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 10px;
  padding: 0 2px;
}

.section-badge {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  flex-shrink: 0;
}

.section-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--jm-text);
}

.section-count {
  margin-left: auto;
  font-size: 11px;
  color: var(--jm-text-tertiary);
}

.section-body {
  border-radius: 8px;
  overflow: hidden;
}

/* Rows */
.dashboard-row {
  display: grid;
  width: 100%;
  grid-template-columns: 3px minmax(0, 1fr) auto 20px;
  gap: 14px;
  align-items: center;
  padding: 14px 18px;
  color: inherit;
  text-align: left;
  background: transparent;
  border: 0;
  border-bottom: 1px solid var(--jm-border-light);
  cursor: pointer;
}

.dashboard-row:last-child {
  border-bottom: 0;
}

.dashboard-row:hover {
  background: #f8faff;
}

.dashboard-row.is-static {
  cursor: default;
}

.dashboard-row.is-static:hover {
  background: transparent;
}

.row-urgency {
  width: 3px;
  height: 36px;
  border-radius: 2px;
  flex-shrink: 0;
}

.row-main {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.row-title {
  overflow: hidden;
  font-size: 14px;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row-sub {
  display: flex;
  gap: 4px;
  align-items: center;
  overflow: hidden;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}

.row-time {
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}

.row-time.urgent {
  color: var(--jm-danger);
}

.row-chevron {
  flex-shrink: 0;
}

/* Empty */
.dashboard-empty {
  min-height: 320px;
}

.dashboard-empty .empty-title {
  margin-bottom: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--jm-text);
}

/* Loading */
.dashboard-loading {
  padding-top: 10px;
}

/* Responsive */
@media (max-width: 700px) {
  .stat-strip {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0;
  }

  .stat-pill {
    padding: 10px 12px;
    border-right: 1px solid var(--jm-border-light);
    border-bottom: 1px solid var(--jm-border-light);
  }

  .stat-pill:nth-child(even) {
    border-right: 0;
  }

  .stat-pill:nth-child(n+3) {
    border-bottom: 0;
  }

  .dashboard-row {
    grid-template-columns: 3px minmax(0, 1fr) auto;
    gap: 10px;
    padding: 12px 14px;
  }

  .row-chevron {
    display: none;
  }

  .row-meta {
    gap: 4px;
  }
}
</style>
