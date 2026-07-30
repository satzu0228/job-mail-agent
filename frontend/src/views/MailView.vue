<script setup lang="ts">
import {
  Connection,
  Document,
  Download,
  Files,
  Link,
  Loading,
  Refresh,
  Search,
  User,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { emailAccountApi, emailApi } from '@/api'
import { getApiErrorMessage } from '@/api/http'
import { categoryMeta, priorityMeta } from '@/utils/dictionaries'
import { formatDateTime, recipientText } from '@/utils/format'
import type { EmailAccount, EmailDetail, EmailListItem, WorkflowRun } from '@/types/api'

const route = useRoute()
const router = useRouter()

const emails = ref<EmailListItem[]>([])
const accounts = ref<EmailAccount[]>([])
const selectedAccountId = ref<number | null>(null)
const selectedEmail = ref<EmailDetail | null>(null)
const activeFilter = ref<'all' | 'linked' | 'unlinked'>('all')
const activeDetailTab = ref('content')
const keyword = ref('')
const loadingList = ref(false)
const loadingDetail = ref(false)
const syncing = ref(false)
const processing = ref(false)
const downloadingAttachment = ref<number | null>(null)
const workflow = ref<WorkflowRun | null>(null)

const filteredEmails = computed(() => {
  const normalized = keyword.value.trim().toLowerCase()
  return emails.value.filter((email) => {
    if (selectedAccountId.value && email.account_id !== selectedAccountId.value) return false
    if (activeFilter.value === 'linked' && !email.application_id) return false
    if (activeFilter.value === 'unlinked' && email.application_id) return false
    if (!normalized) return true
    return [email.subject, email.from_name, email.from_address]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(normalized))
  })
})

const selectedId = computed(() => Number(route.params.emailId) || null)

async function loadBaseData() {
  loadingList.value = true
  try {
    const [emailRows, accountRows] = await Promise.all([
      emailApi.list(),
      emailAccountApi.list(),
    ])
    emails.value = emailRows
    accounts.value = accountRows
    selectedAccountId.value ??= accountRows.find((account) => account.is_active)?.id ?? null

    const routeId = selectedId.value
    const firstId =
      routeId && emailRows.some((email) => email.id === routeId)
        ? routeId
        : filteredEmails.value[0]?.id
    if (firstId) await selectEmail(firstId, false)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    loadingList.value = false
  }
}

async function selectEmail(id: number, updateRoute = true) {
  if (loadingDetail.value) return
  loadingDetail.value = true
  workflow.value = null
  try {
    selectedEmail.value = await emailApi.detail(id)
    activeDetailTab.value = 'content'
    if (updateRoute && selectedId.value !== id) {
      await router.replace({ name: 'mail', params: { emailId: id } })
    }
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    loadingDetail.value = false
  }
}

async function syncAccount() {
  if (!selectedAccountId.value) {
    ElMessage.warning('请先在邮箱设置中添加账户')
    return
  }
  syncing.value = true
  try {
    const result = await emailAccountApi.sync(selectedAccountId.value)
    ElMessage.success(`同步完成，新增 ${result.created} 封邮件`)
    await loadBaseData()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    syncing.value = false
  }
}

async function startWorkflow() {
  if (!selectedEmail.value) return
  processing.value = true
  try {
    workflow.value = await emailApi.startWorkflow(selectedEmail.value.id)
    selectedEmail.value = await emailApi.detail(selectedEmail.value.id)
    if (workflow.value.pending_review_task_id) {
      ElMessage.success('智能处理已暂停，等待你的审核')
    } else if (workflow.value.status === 'SUCCEEDED') {
      ElMessage.success('智能处理已完成')
    }
    activeDetailTab.value = 'analysis'
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    processing.value = false
  }
}

function openReview() {
  const taskId = workflow.value?.pending_review_task_id
  void router.push(taskId ? `/reviews/${taskId}` : '/reviews')
}

function attachmentName(item: Record<string, unknown>, index: number): string {
  return String(item.filename ?? item.name ?? `附件 ${index + 1}`)
}

async function downloadAttachment(attachment: Record<string, unknown>, index: number) {
  if (!selectedEmail.value) return
  downloadingAttachment.value = index
  try {
    const response = await emailApi.downloadAttachment(selectedEmail.value.id, index)
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = attachmentName(attachment, index)
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    downloadingAttachment.value = null
  }
}

watch(
  () => route.params.emailId,
  (value) => {
    const id = Number(value)
    if (id && id !== selectedEmail.value?.id) void selectEmail(id, false)
  },
)

onMounted(loadBaseData)
</script>

<template>
  <div class="mail-page">
    <section class="mail-list-pane">
      <div class="mail-controls">
        <div class="account-row">
          <ElSelect
            v-model="selectedAccountId"
            class="account-select"
            placeholder="选择邮箱"
            :disabled="accounts.length === 0"
          >
            <ElOption
              v-for="account in accounts"
              :key="account.id"
              :label="account.email_address_masked"
              :value="account.id"
            />
          </ElSelect>
          <ElButton
            :icon="Refresh"
            :loading="syncing"
            title="同步收件箱"
            @click="syncAccount"
          />
        </div>

        <ElInput v-model="keyword" clearable :prefix-icon="Search" placeholder="搜索主题或发件人" />

        <div class="filter-tabs" role="tablist" aria-label="邮件筛选">
          <button
            v-for="item in [
              { value: 'all', label: '全部' },
              { value: 'linked', label: '已关联' },
              { value: 'unlinked', label: '待关联' },
            ]"
            :key="item.value"
            type="button"
            :class="{ active: activeFilter === item.value }"
            @click="activeFilter = item.value as typeof activeFilter"
          >
            {{ item.label }}
          </button>
        </div>
      </div>

      <div v-loading="loadingList" class="mail-list">
        <button
          v-for="email in filteredEmails"
          :key="email.id"
          class="mail-row"
          :class="{ selected: selectedEmail?.id === email.id }"
          type="button"
          @click="selectEmail(email.id)"
        >
          <div class="mail-row-head">
            <strong class="truncate">{{ email.from_name || email.from_address }}</strong>
            <time>{{ formatDateTime(email.received_at).slice(5) }}</time>
          </div>
          <div class="mail-subject truncate">{{ email.subject || '（无主题）' }}</div>
          <div class="mail-meta">
            <span v-if="email.application_id" class="linked-mark">
              <ElIcon><Link /></ElIcon> 已关联
            </span>
            <span v-else>待处理</span>
            <span v-if="email.parse_status !== 'SUCCEEDED'" class="parse-warning">
              {{ email.parse_status === 'FAILED' ? '解析失败' : '解析不完整' }}
            </span>
          </div>
        </button>

        <div v-if="!loadingList && filteredEmails.length === 0" class="empty-state">
          <div>
            <p>没有符合条件的邮件</p>
            <ElButton v-if="accounts.length" type="primary" plain @click="syncAccount">
              同步收件箱
            </ElButton>
            <ElButton v-else type="primary" plain @click="router.push('/settings/mailboxes')">
              添加邮箱
            </ElButton>
          </div>
        </div>
      </div>
    </section>

    <section v-loading="loadingDetail" class="mail-detail-pane">
      <template v-if="selectedEmail">
        <header class="detail-header">
          <div class="detail-title">
            <h2>{{ selectedEmail.subject || '（无主题）' }}</h2>
            <div class="sender-line">
              <span class="sender-avatar">{{ (selectedEmail.from_name || '邮').slice(0, 1) }}</span>
              <div>
                <strong>{{ selectedEmail.from_name || selectedEmail.from_address }}</strong>
                <span>{{ selectedEmail.from_address }}</span>
              </div>
              <time>{{ formatDateTime(selectedEmail.received_at) }}</time>
            </div>
          </div>

          <div v-if="selectedEmail.current_analysis" class="analysis-strip">
            <div class="ai-label"><span /> AI 分析</div>
            <ElTag
              :type="categoryMeta[selectedEmail.current_analysis.category].type"
              effect="light"
            >
              {{ categoryMeta[selectedEmail.current_analysis.category].label }}
            </ElTag>
            <ElTag
              :type="priorityMeta[selectedEmail.current_analysis.priority].type"
              effect="plain"
            >
              {{ priorityMeta[selectedEmail.current_analysis.priority].label }}优先级
            </ElTag>
            <p class="truncate">
              {{ selectedEmail.current_analysis.summary || '分析已完成，暂无摘要' }}
            </p>
          </div>
          <div v-else class="analysis-strip empty-analysis">
            <div class="ai-label"><span /> 尚未分析</div>
            <p>运行智能处理后，系统会分类邮件并提取求职信息。</p>
          </div>
        </header>

        <ElTabs v-model="activeDetailTab" class="detail-tabs">
          <ElTabPane label="邮件内容" name="content">
            <div class="tab-scroll">
              <div class="recipient-row">
                <span>收件人</span>
                <span>{{ selectedEmail.to_recipients.map(recipientText).join('，') || '—' }}</span>
              </div>
              <div
                v-if="selectedEmail.html_sanitized"
                class="email-html"
                v-html="selectedEmail.html_sanitized"
              />
              <pre v-else class="email-plain">{{ selectedEmail.plain_body || '邮件正文为空' }}</pre>
            </div>
          </ElTabPane>

          <ElTabPane label="AI 分析" name="analysis">
            <div class="tab-scroll analysis-content">
              <template v-if="selectedEmail.current_analysis">
                <div class="analysis-grid">
                  <div>
                    <span>公司</span>
                    <strong>{{ selectedEmail.current_analysis.company_name || '待确认' }}</strong>
                  </div>
                  <div>
                    <span>岗位</span>
                    <strong>{{ selectedEmail.current_analysis.position_name || '待确认' }}</strong>
                  </div>
                  <div>
                    <span>事件时间</span>
                    <strong>{{ formatDateTime(selectedEmail.current_analysis.event_time) }}</strong>
                  </div>
                  <div>
                    <span>截止时间</span>
                    <strong>{{ formatDateTime(selectedEmail.current_analysis.deadline_at) }}</strong>
                  </div>
                </div>

                <section class="analysis-section">
                  <h3>处理判断</h3>
                  <dl>
                    <div>
                      <dt>求职相关</dt>
                      <dd>{{ selectedEmail.current_analysis.is_job_related ? '是' : '否' }}</dd>
                    </div>
                    <div>
                      <dt>建议回复</dt>
                      <dd>{{ selectedEmail.current_analysis.should_reply ? '需要' : '不需要' }}</dd>
                    </div>
                    <div>
                      <dt>分类置信度</dt>
                      <dd>
                        {{ Math.round(selectedEmail.current_analysis.classification_confidence * 100) }}%
                      </dd>
                    </div>
                  </dl>
                </section>

                <section
                  v-if="selectedEmail.current_analysis.missing_fields.length"
                  class="analysis-section"
                >
                  <h3>待确认信息</h3>
                  <div class="chip-list">
                    <span v-for="field in selectedEmail.current_analysis.missing_fields" :key="field">
                      {{ field }}
                    </span>
                  </div>
                </section>

                <ElCollapse class="technical-collapse">
                  <ElCollapseItem title="查看字段证据和完整结构化结果">
                    <h4>字段证据</h4>
                    <pre>{{ JSON.stringify(selectedEmail.current_analysis.evidence_json, null, 2) }}</pre>
                    <h4>抽取结果</h4>
                    <pre>{{ JSON.stringify(selectedEmail.current_analysis.extraction_json, null, 2) }}</pre>
                  </ElCollapseItem>
                </ElCollapse>
              </template>
              <div v-else class="empty-state">
                <div>
                  <p>这封邮件还没有 AI 分析结果</p>
                  <ElButton type="primary" :loading="processing" @click="startWorkflow">
                    启动智能处理
                  </ElButton>
                </div>
              </div>
            </div>
          </ElTabPane>

          <ElTabPane :label="`附件 ${selectedEmail.attachment_metadata.length}`" name="attachments">
            <div class="tab-scroll attachment-list">
              <div
                v-for="(attachment, index) in selectedEmail.attachment_metadata"
                :key="index"
                class="attachment-row"
              >
                <ElIcon :size="20"><Document /></ElIcon>
                <div>
                  <strong>{{ attachmentName(attachment, index) }}</strong>
                  <span>附件按不可信输入下载，系统不会自动执行其内容</span>
                </div>
                <ElButton
                  class="attachment-download"
                  :icon="Download"
                  :loading="downloadingAttachment === index"
                  :disabled="Boolean(attachment.download_skipped)"
                  @click="downloadAttachment(attachment, index)"
                >
                  {{ attachment.download_skipped ? '超过安全上限' : '下载' }}
                </ElButton>
              </div>
              <div v-if="selectedEmail.attachment_metadata.length === 0" class="empty-state">
                这封邮件没有附件
              </div>
            </div>
          </ElTabPane>
        </ElTabs>

        <footer class="detail-actions">
          <div v-if="workflow" class="workflow-status">
            <ElIcon :class="{ spinning: processing }"><component :is="processing ? Loading : Connection" /></ElIcon>
            <span>
              {{
                workflow.status === 'WAITING_REVIEW'
                  ? '等待人工审核'
                  : workflow.status === 'SUCCEEDED'
                    ? '处理完成'
                    : workflow.status
              }}
            </span>
          </div>
          <span v-else />
          <div>
            <ElButton
              v-if="workflow?.pending_review_task_id"
              type="primary"
              plain
              @click="openReview"
            >
              前往审核
            </ElButton>
            <ElButton type="primary" :loading="processing" @click="startWorkflow">
              {{ selectedEmail.current_analysis ? '重新智能处理' : '启动智能处理' }}
            </ElButton>
          </div>
        </footer>
      </template>

      <div v-else class="empty-detail">
        <ElIcon :size="34"><Files /></ElIcon>
        <p>从左侧选择一封邮件</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.mail-page {
  display: grid;
  height: 100%;
  min-height: 0;
  grid-template-columns: 360px minmax(0, 1fr);
  background: #fff;
}

.mail-list-pane {
  display: grid;
  min-width: 0;
  min-height: 0;
  grid-template-rows: auto minmax(0, 1fr);
  border-right: 1px solid var(--jm-border);
}

.mail-controls {
  display: grid;
  gap: 12px;
  padding: 16px;
  border-bottom: 1px solid var(--jm-border-light);
}

.account-row {
  display: flex;
  gap: 8px;
}

.account-select {
  min-width: 0;
  flex: 1;
}

.filter-tabs {
  display: flex;
  gap: 4px;
}

.filter-tabs button {
  padding: 6px 10px;
  color: var(--jm-text-secondary);
  font-size: 13px;
  background: transparent;
  border: 0;
  border-radius: 5px;
  cursor: pointer;
}

.filter-tabs button:hover,
.filter-tabs button.active {
  color: #245bdb;
  background: var(--jm-primary-soft);
}

.mail-list {
  min-height: 0;
  overflow-y: auto;
}

.mail-row {
  display: grid;
  width: 100%;
  gap: 7px;
  padding: 14px 16px;
  color: inherit;
  text-align: left;
  background: #fff;
  border: 0;
  border-bottom: 1px solid var(--jm-border-light);
  cursor: pointer;
}

.mail-row:hover {
  background: #f8f9fa;
}

.mail-row.selected {
  background: #f0f5ff;
  box-shadow: inset 3px 0 var(--jm-primary);
}

.mail-row-head {
  display: flex;
  gap: 10px;
  align-items: baseline;
  justify-content: space-between;
}

.mail-row-head strong {
  font-size: 14px;
}

.mail-row-head time {
  flex: 0 0 auto;
  color: var(--jm-text-tertiary);
  font-size: 11px;
}

.mail-subject {
  font-size: 13px;
  color: var(--jm-text-secondary);
}

.mail-meta {
  display: flex;
  gap: 10px;
  align-items: center;
  color: var(--jm-text-tertiary);
  font-size: 11px;
}

.linked-mark {
  display: inline-flex;
  gap: 3px;
  align-items: center;
  color: #356cc5;
}

.parse-warning {
  color: var(--jm-warning);
}

.mail-detail-pane {
  position: relative;
  display: grid;
  min-width: 0;
  min-height: 0;
  grid-template-rows: auto minmax(0, 1fr) auto;
}

.detail-header {
  padding: 20px 24px 0;
}

.detail-title h2 {
  margin: 0 0 16px;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.35;
}

.sender-line {
  display: flex;
  gap: 10px;
  align-items: center;
}

.sender-avatar {
  display: grid;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  color: #245bdb;
  font-size: 14px;
  font-weight: 600;
  background: var(--jm-primary-soft);
  border-radius: 50%;
  place-items: center;
}

.sender-line > div {
  display: grid;
  min-width: 0;
}

.sender-line strong {
  font-size: 13px;
}

.sender-line span {
  color: var(--jm-text-tertiary);
  font-size: 11px;
}

.sender-line time {
  margin-left: auto;
  color: var(--jm-text-tertiary);
  font-size: 12px;
}

.analysis-strip {
  display: flex;
  min-height: 44px;
  gap: 8px;
  align-items: center;
  margin-top: 18px;
  padding: 8px 12px;
  background: #f6f8ff;
  border: 1px solid #e2e9ff;
  border-radius: 7px;
}

.analysis-strip p {
  min-width: 0;
  margin: 0 0 0 2px;
  color: var(--jm-text-secondary);
  font-size: 12px;
}

.analysis-strip.empty-analysis {
  background: #f8f9fa;
  border-color: var(--jm-border-light);
}

.ai-label {
  display: flex;
  flex: 0 0 auto;
  gap: 6px;
  align-items: center;
  color: #5a47b8;
  font-size: 12px;
  font-weight: 600;
}

.ai-label span {
  width: 6px;
  height: 6px;
  background: #7b61d1;
  border-radius: 50%;
}

.detail-tabs {
  min-height: 0;
  margin-top: 6px;
}

.detail-tabs :deep(.el-tabs__header) {
  margin: 0;
  padding: 0 24px;
}

.detail-tabs :deep(.el-tabs__content),
.detail-tabs :deep(.el-tab-pane) {
  height: 100%;
  min-height: 0;
}

.detail-tabs :deep(.el-tabs__content) {
  height: calc(100% - 40px);
}

.tab-scroll {
  height: 100%;
  padding: 20px 24px;
  overflow: auto;
}

.recipient-row {
  display: flex;
  gap: 14px;
  margin-bottom: 18px;
  padding-bottom: 12px;
  color: var(--jm-text-secondary);
  font-size: 12px;
  border-bottom: 1px solid var(--jm-border-light);
}

.recipient-row span:first-child {
  color: var(--jm-text-tertiary);
}

.email-html {
  max-width: 860px;
  color: #25272b;
  font-size: 14px;
  line-height: 1.75;
}

.email-html :deep(img) {
  max-width: 100%;
}

.email-plain {
  margin: 0;
  color: #25272b;
  font: inherit;
  font-size: 14px;
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
}

.analysis-content {
  max-width: 960px;
}

.analysis-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  border: 1px solid var(--jm-border-light);
  border-radius: 7px;
  overflow: hidden;
}

.analysis-grid > div {
  display: grid;
  gap: 5px;
  padding: 14px 16px;
  border-right: 1px solid var(--jm-border-light);
  border-bottom: 1px solid var(--jm-border-light);
}

.analysis-grid > div:nth-child(even) {
  border-right: 0;
}

.analysis-grid > div:nth-last-child(-n + 2) {
  border-bottom: 0;
}

.analysis-grid span {
  color: var(--jm-text-tertiary);
  font-size: 12px;
}

.analysis-grid strong {
  font-size: 14px;
  font-weight: 500;
}

.analysis-section {
  margin-top: 24px;
}

.analysis-section h3 {
  margin: 0 0 12px;
  font-size: 14px;
}

.analysis-section dl {
  display: flex;
  flex-wrap: wrap;
  gap: 28px;
  margin: 0;
}

.analysis-section dl div {
  display: flex;
  gap: 8px;
}

.analysis-section dt {
  color: var(--jm-text-tertiary);
}

.analysis-section dd {
  margin: 0;
}

.chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip-list span {
  padding: 5px 9px;
  color: #9c621a;
  font-size: 12px;
  background: #fff7e8;
  border-radius: 5px;
}

.technical-collapse {
  margin-top: 22px;
}

.technical-collapse h4 {
  margin: 12px 0 6px;
}

.technical-collapse pre {
  padding: 12px;
  overflow: auto;
  font-size: 11px;
  background: #f6f7f8;
  border-radius: 6px;
}

.attachment-list {
  display: grid;
  align-content: start;
  gap: 8px;
}

.attachment-row {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
  border: 1px solid var(--jm-border-light);
  border-radius: 7px;
}

.attachment-row > div {
  display: grid;
  gap: 3px;
}

.attachment-download {
  margin-left: auto;
}

.attachment-row span {
  color: var(--jm-text-tertiary);
  font-size: 11px;
}

.detail-actions {
  display: flex;
  min-height: 64px;
  align-items: center;
  justify-content: space-between;
  padding: 10px 24px;
  background: #fff;
  border-top: 1px solid var(--jm-border-light);
}

.workflow-status {
  display: flex;
  gap: 7px;
  align-items: center;
  color: var(--jm-text-secondary);
  font-size: 12px;
}

.spinning {
  animation: rotate 1s linear infinite;
}

.empty-detail {
  display: grid;
  grid-row: 1 / -1;
  color: var(--jm-text-tertiary);
  place-content: center;
  text-align: center;
}

@keyframes rotate {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 960px) {
  .mail-page {
    grid-template-columns: 310px minmax(0, 1fr);
  }
}

@media (max-width: 720px) {
  .mail-page {
    grid-template-columns: 1fr;
  }

  .mail-detail-pane {
    position: absolute;
    inset: 64px 0 0 56px;
    z-index: 20;
    display: none;
    background: #fff;
  }

  .mail-detail-pane:has(.detail-header) {
    display: grid;
  }
}
</style>
