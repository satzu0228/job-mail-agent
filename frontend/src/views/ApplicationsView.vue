<script setup lang="ts">
import { Plus, Search } from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { applicationApi, emailApi, taskApi } from '@/api'
import { getApiErrorMessage } from '@/api/http'
import { stageMeta, taskStatusMeta, taskTypeMeta } from '@/utils/dictionaries'
import { formatDate, formatDateTime, formatRelativeDate, taskTime } from '@/utils/format'
import type {
  EmailListItem,
  JobApplication,
  JobApplicationCreate,
  Task,
} from '@/types/api'

type ProgressFilter = 'all' | 'active' | 'closed'

const applications = ref<JobApplication[]>([])
const tasks = ref<Task[]>([])
const emails = ref<EmailListItem[]>([])
const loading = ref(false)
const keyword = ref('')
const progressFilter = ref<ProgressFilter>('all')
const stageFilter = ref('')
const drawerVisible = ref(false)
const createVisible = ref(false)
const selected = ref<JobApplication | null>(null)
const saving = ref(false)
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

function relatedTasks(id: number): Task[] {
  return tasks.value
    .filter((task) => task.application_id === id)
    .sort((a, b) => String(taskTime(a)).localeCompare(String(taskTime(b))))
}

function stageLabel(stage: JobApplication['current_stage']): string {
  return stageMeta[stage].label
}

function stageType(stage: JobApplication['current_stage']) {
  return stageMeta[stage].type
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
  loading.value = true
  try {
    const [applicationRows, taskRows, emailRows] = await Promise.all([
      applicationApi.list(),
      taskApi.list(),
      emailApi.list(),
    ])
    applications.value = applicationRows
    tasks.value = taskRows
    emails.value = emailRows
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function openApplication(application: JobApplication) {
  selected.value = application
  Object.assign(editForm, {
    company_name: application.company_name,
    position_name: application.position_name,
    location: application.location ?? '',
    applied_at: application.applied_at ?? '',
    contact_name: application.contact_name ?? '',
    contact_email: application.contact_email ?? '',
    notes: application.notes ?? '',
  })
  drawerVisible.value = true
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
      applied_at: editForm.applied_at || null,
      contact_name: editForm.contact_name || null,
      contact_email: editForm.contact_email || null,
      notes: editForm.notes || null,
    })
    const index = applications.value.findIndex((item) => item.id === updated.id)
    if (index >= 0) applications.value[index] = updated
    selected.value = updated
    ElMessage.success('申请信息已保存')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    saving.value = false
  }
}

async function createApplication() {
  if (!(await createFormRef.value?.validate())) return
  saving.value = true
  try {
    await applicationApi.create(createForm)
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
        <ElTableColumn label="当前阶段" width="110">
          <template #default="{ row }">
            <ElTag :type="stageType(row.current_stage)" effect="light">
              {{ stageLabel(row.current_stage) }}
            </ElTag>
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
                <strong>{{ nextTask(row.id)!.title }}</strong>
                <span>{{ formatRelativeDate(taskTime(nextTask(row.id)!)) }}</span>
              </div>
            </div>
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
            <p>{{ keyword || stageFilter ? '没有符合筛选条件的申请' : '还没有求职申请' }}</p>
            <ElButton v-if="!keyword && !stageFilter" type="primary" plain @click="createVisible = true">
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
          <div>
            <span>当前阶段</span>
            <ElTag :type="stageMeta[selected.current_stage].type" effect="light" size="large">
              {{ stageMeta[selected.current_stage].label }}
            </ElTag>
          </div>
          <p>阶段来自用户确认后的业务状态，不能在此直接修改。</p>
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
                    type="datetime"
                    value-format="YYYY-MM-DDTHH:mm:ssZ"
                    placeholder="选择投递时间"
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
                  <strong>{{ task.title }}</strong>
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
        </ElTabs>
      </div>
    </ElDrawer>

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
              type="datetime"
              value-format="YYYY-MM-DDTHH:mm:ssZ"
              placeholder="选择投递时间"
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
  padding: 16px 0;
  border-bottom: 1px solid var(--jm-border-light);
}

.drawer-stage > div {
  display: flex;
  gap: 10px;
  align-items: center;
}

.drawer-stage > div > span {
  color: var(--jm-text-secondary);
  font-size: 12px;
}

.drawer-stage p {
  max-width: 240px;
  margin: 0;
  color: var(--jm-text-tertiary);
  font-size: 11px;
  text-align: right;
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

@media (max-width: 560px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
