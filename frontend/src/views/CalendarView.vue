<script setup lang="ts">
import { Calendar as CalendarIcon, List, Location, Link } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

import { applicationApi, taskApi } from '@/api'
import { getApiErrorMessage } from '@/api/http'
import { taskStatusMeta, taskTypeMeta } from '@/utils/dictionaries'
import { formatDateTime, formatRelativeDate, taskTime } from '@/utils/format'
import type { JobApplication, Task, TaskStatus } from '@/types/api'

type ViewMode = 'list' | 'month'

const tasks = ref<Task[]>([])
const applications = ref<JobApplication[]>([])
const loading = ref(false)
const viewMode = ref<ViewMode>('list')
const calendarDate = ref(new Date())
const selected = ref<Task | null>(null)
const drawerVisible = ref(false)
const updating = ref(false)
const statusFilter = ref('')

const visibleTasks = computed(() =>
  tasks.value
    .filter((task) => !statusFilter.value || task.status === statusFilter.value)
    .sort((a, b) => {
      const aTime = taskTime(a)
      const bTime = taskTime(b)
      if (!aTime) return 1
      if (!bTime) return -1
      return aTime.localeCompare(bTime)
    }),
)

const upcomingTasks = computed(() => {
  const threshold = dayjs().subtract(1, 'day').startOf('day')
  return visibleTasks.value.filter((task) => {
    const value = taskTime(task)
    return !value || dayjs(value).isAfter(threshold)
  })
})

const confirmedCount = computed(
  () => tasks.value.filter((task) => task.status === 'CONFIRMED').length,
)
const pendingCount = computed(() => tasks.value.filter((task) => task.status === 'PENDING').length)

function applicationName(id: number | null): string {
  if (!id) return '未关联申请'
  const application = applications.value.find((item) => item.id === id)
  return application ? `${application.company_name} · ${application.position_name}` : '申请记录'
}

function tasksForDate(date: string): Task[] {
  return visibleTasks.value.filter((task) => {
    const value = taskTime(task)
    return value && dayjs(value).format('YYYY-MM-DD') === date
  })
}

function openTask(task: Task) {
  selected.value = task
  drawerVisible.value = true
}

async function loadData() {
  loading.value = true
  try {
    const [taskRows, applicationRows] = await Promise.all([
      taskApi.list(),
      applicationApi.list(),
    ])
    tasks.value = taskRows
    applications.value = applicationRows
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function updateStatus(status: TaskStatus) {
  if (!selected.value) return
  updating.value = true
  try {
    const updated = await taskApi.update(selected.value.id, {
      version: selected.value.version,
      status,
    })
    const index = tasks.value.findIndex((task) => task.id === updated.id)
    if (index >= 0) tasks.value[index] = updated
    selected.value = updated
    ElMessage.success('日程状态已更新')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    updating.value = false
  }
}

onMounted(loadData)
</script>

<template>
  <div class="page-shell calendar-page">
    <div class="page-toolbar">
      <div class="toolbar-group">
        <div class="view-switch">
          <button
            type="button"
            :class="{ active: viewMode === 'list' }"
            @click="viewMode = 'list'"
          >
            <ElIcon><List /></ElIcon>近期任务
          </button>
          <button
            type="button"
            :class="{ active: viewMode === 'month' }"
            @click="viewMode = 'month'"
          >
            <ElIcon><CalendarIcon /></ElIcon>月历
          </button>
        </div>
        <span class="summary-text">{{ confirmedCount }} 项已确认 · {{ pendingCount }} 项待确认</span>
      </div>
      <ElSelect v-model="statusFilter" clearable placeholder="全部状态" class="status-filter">
        <ElOption
          v-for="(meta, value) in taskStatusMeta"
          :key="value"
          :label="meta.label"
          :value="value"
        />
      </ElSelect>
    </div>

    <section v-loading="loading" class="surface calendar-surface">
      <div v-if="viewMode === 'list'" class="schedule-list">
        <button
          v-for="task in upcomingTasks"
          :key="task.id"
          type="button"
          class="schedule-row"
          @click="openTask(task)"
        >
          <div class="schedule-date">
            <template v-if="taskTime(task)">
              <strong>{{ dayjs(taskTime(task)).format('DD') }}</strong>
              <span>{{ dayjs(taskTime(task)).format('MM月') }}</span>
            </template>
            <template v-else>
              <strong>待</strong>
              <span>确认</span>
            </template>
          </div>
          <span
            class="type-line"
            :style="{ background: taskTypeMeta[task.task_type].color }"
          />
          <div class="schedule-main">
            <div>
              <strong>{{ task.title }}</strong>
              <ElTag :type="taskStatusMeta[task.status].type" effect="plain" size="small">
                {{ taskStatusMeta[task.status].label }}
              </ElTag>
            </div>
            <span>{{ applicationName(task.application_id) }}</span>
          </div>
          <div class="schedule-info">
            <strong>{{ formatRelativeDate(taskTime(task)) }}</strong>
            <span>{{ task.location || task.raw_time_text || '暂无地点信息' }}</span>
          </div>
        </button>

        <div v-if="upcomingTasks.length === 0" class="empty-state">
          <div>
            <p>近期没有日程任务</p>
            <span class="quiet">邮件中的面试和截止时间通过审核后会显示在这里</span>
          </div>
        </div>
      </div>

      <ElCalendar v-else v-model="calendarDate" class="month-calendar">
        <template #date-cell="{ data }">
          <div class="calendar-cell">
            <span class="day-number">{{ dayjs(data.day).format('D') }}</span>
            <button
              v-for="task in tasksForDate(data.day).slice(0, 3)"
              :key="task.id"
              type="button"
              class="calendar-event"
              :style="{ '--event-color': taskTypeMeta[task.task_type].color }"
              :title="task.title"
              @click.stop="openTask(task)"
            >
              {{ task.title }}
            </button>
            <span v-if="tasksForDate(data.day).length > 3" class="more-events">
              另有 {{ tasksForDate(data.day).length - 3 }} 项
            </span>
          </div>
        </template>
      </ElCalendar>
    </section>

    <ElDrawer
      v-model="drawerVisible"
      size="min(480px, 92vw)"
      :title="selected?.title || '日程详情'"
    >
      <div v-if="selected" class="task-drawer">
        <div class="task-heading">
          <span
            class="task-type-icon"
            :style="{ background: taskTypeMeta[selected.task_type].color }"
          />
          <div>
            <strong>{{ taskTypeMeta[selected.task_type].label }}</strong>
            <span>{{ applicationName(selected.application_id) }}</span>
          </div>
          <ElTag :type="taskStatusMeta[selected.status].type" effect="light">
            {{ taskStatusMeta[selected.status].label }}
          </ElTag>
        </div>

        <dl class="task-details">
          <div>
            <dt>标准时间</dt>
            <dd>{{ formatDateTime(taskTime(selected)) }}</dd>
          </div>
          <div>
            <dt>原始时间</dt>
            <dd>{{ selected.raw_time_text || '—' }}</dd>
          </div>
          <div>
            <dt>来源时区</dt>
            <dd>{{ selected.source_timezone || '—' }}</dd>
          </div>
          <div>
            <dt>地点</dt>
            <dd>{{ selected.location || '—' }}</dd>
          </div>
          <div>
            <dt>说明</dt>
            <dd>{{ selected.description || '—' }}</dd>
          </div>
        </dl>

        <a
          v-if="selected.meeting_url"
          :href="selected.meeting_url"
          target="_blank"
          rel="noopener noreferrer"
          class="meeting-link"
        >
          <ElIcon><Link /></ElIcon>
          打开会议链接
        </a>
        <RouterLink
          v-if="selected.source_email_id"
          :to="`/mail/${selected.source_email_id}`"
          class="source-link"
        >
          查看来源邮件
        </RouterLink>
      </div>
      <template v-if="selected" #footer>
        <div class="task-actions">
          <ElButton
            v-if="selected.status !== 'CANCELLED'"
            :disabled="updating"
            @click="updateStatus('CANCELLED')"
          >
            取消任务
          </ElButton>
          <ElButton
            v-if="selected.status !== 'COMPLETED'"
            type="primary"
            :loading="updating"
            @click="updateStatus(selected.status === 'PENDING' ? 'CONFIRMED' : 'COMPLETED')"
          >
            {{ selected.status === 'PENDING' ? '确认日程' : '标记完成' }}
          </ElButton>
        </div>
      </template>
    </ElDrawer>
  </div>
</template>

<style scoped>
.calendar-page {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
}

.view-switch {
  display: flex;
  padding: 3px;
  background: #eaedf0;
  border-radius: 7px;
}

.view-switch button {
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 6px 12px;
  color: var(--jm-text-secondary);
  font-size: 13px;
  background: transparent;
  border: 0;
  border-radius: 5px;
  cursor: pointer;
}

.view-switch button.active {
  color: var(--jm-text);
  background: #fff;
  box-shadow: 0 1px 2px rgb(31 35 41 / 8%);
}

.summary-text {
  color: var(--jm-text-tertiary);
  font-size: 12px;
}

.status-filter {
  width: 130px;
}

.calendar-surface {
  min-height: 0;
  overflow: auto;
}

.schedule-list {
  max-width: 980px;
  margin: 0 auto;
  padding: 10px 24px 28px;
}

.schedule-row {
  display: grid;
  width: 100%;
  grid-template-columns: 48px 3px minmax(0, 1fr) minmax(180px, 0.6fr);
  gap: 14px;
  align-items: center;
  padding: 16px 8px;
  color: inherit;
  text-align: left;
  background: transparent;
  border: 0;
  border-bottom: 1px solid var(--jm-border-light);
  cursor: pointer;
}

.schedule-row:hover {
  background: #f8faff;
}

.schedule-date {
  display: grid;
  color: var(--jm-text-secondary);
  text-align: center;
}

.schedule-date strong {
  font-size: 20px;
  line-height: 1.1;
}

.schedule-date span {
  font-size: 10px;
}

.type-line {
  width: 3px;
  height: 36px;
  border-radius: 2px;
}

.schedule-main,
.schedule-info {
  display: grid;
  min-width: 0;
  gap: 4px;
}

.schedule-main > div {
  display: flex;
  gap: 8px;
  align-items: center;
}

.schedule-main strong {
  overflow: hidden;
  font-size: 14px;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.schedule-main > span,
.schedule-info span {
  color: var(--jm-text-tertiary);
  font-size: 11px;
}

.schedule-info strong {
  font-size: 12px;
  font-weight: 500;
}

.month-calendar {
  min-width: 760px;
}

.month-calendar :deep(.el-calendar__header) {
  padding: 16px 20px;
}

.month-calendar :deep(.el-calendar__body) {
  padding: 0 16px 16px;
}

.month-calendar :deep(.el-calendar-table .el-calendar-day) {
  height: 110px;
  padding: 0;
}

.calendar-cell {
  height: 100%;
  padding: 7px;
  overflow: hidden;
}

.day-number {
  display: block;
  margin-bottom: 5px;
  color: var(--jm-text-secondary);
  font-size: 12px;
}

.calendar-event {
  display: block;
  width: 100%;
  margin-bottom: 3px;
  padding: 3px 5px;
  overflow: hidden;
  color: var(--jm-text);
  font-size: 10px;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
  background: color-mix(in srgb, var(--event-color) 10%, white);
  border: 0;
  border-left: 2px solid var(--event-color);
  border-radius: 3px;
  cursor: pointer;
}

.more-events {
  color: var(--jm-text-tertiary);
  font-size: 10px;
}

.task-drawer {
  padding: 20px;
}

.task-heading {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--jm-border-light);
}

.task-type-icon {
  width: 9px;
  height: 9px;
  border-radius: 50%;
}

.task-heading > div {
  display: grid;
  gap: 3px;
}

.task-heading strong {
  font-size: 13px;
}

.task-heading span {
  color: var(--jm-text-tertiary);
  font-size: 11px;
}

.task-details {
  margin: 20px 0;
}

.task-details div {
  display: grid;
  grid-template-columns: 90px minmax(0, 1fr);
  padding: 9px 0;
}

.task-details dt {
  color: var(--jm-text-tertiary);
  font-size: 12px;
}

.task-details dd {
  margin: 0;
  font-size: 13px;
  white-space: pre-wrap;
}

.meeting-link,
.source-link {
  display: flex;
  gap: 7px;
  align-items: center;
  margin-top: 8px;
  padding: 10px 12px;
  color: var(--jm-primary);
  font-size: 13px;
  background: var(--jm-primary-soft);
  border-radius: 6px;
}

.source-link {
  color: var(--jm-text-secondary);
  background: #f5f6f7;
}

.task-actions {
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 700px) {
  .summary-text {
    display: none;
  }

  .schedule-list {
    padding: 8px 12px 20px;
  }

  .schedule-row {
    grid-template-columns: 40px 3px minmax(0, 1fr);
  }

  .schedule-info {
    display: none;
  }
}
</style>
