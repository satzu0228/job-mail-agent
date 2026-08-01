<script setup lang="ts">
import {
  ArrowLeft,
  Connection,
  Document,
  Download,
  Files,
  Link,
  Loading,
  Refresh,
  RefreshLeft,
  Search,
  TakeawayBox,
  User,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { emailAccountApi, emailApi } from '@/api'
import { getApiErrorMessage } from '@/api/http'
import {
  analysisFieldLabel,
  categoryMeta,
  priorityMeta,
  workflowStatusLabels,
} from '@/utils/dictionaries'
import {
  countRemoteEmailImages,
  enhanceSanitizedEmailLinks,
  normalizeContentId,
  revealRemoteEmailImages,
} from '@/utils/emailHtml'
import { formatDateTime, recipientText } from '@/utils/format'
import type { EmailAccount, EmailDetail, EmailListItem, WorkflowRun } from '@/types/api'

const route = useRoute()
const router = useRouter()

const emails = ref<EmailListItem[]>([])
const accounts = ref<EmailAccount[]>([])
const selectedAccountId = ref<number | null>(null)
const selectedEmail = ref<EmailDetail | null>(null)
const directionFilter = ref<'RECEIVED' | 'SENT'>('RECEIVED')
const linkFilter = ref<'all' | 'linked' | 'unlinked'>('all')
const activeDetailTab = ref('content')
const keyword = ref('')
const loadingList = ref(false)
const loadingDetail = ref(false)
const syncing = ref(false)
const processing = ref(false)
const movingEmail = ref(false)
const downloadingAttachment = ref<number | null>(null)
const workflow = ref<WorkflowRun | null>(null)
const externalImageCount = ref(0)
const externalImagesAllowed = ref(false)
const inlineImageUrls = new Set<string>()

const filteredEmails = computed(() => {
  const normalized = keyword.value.trim().toLowerCase()
  return emails.value.filter((email) => {
    if (selectedAccountId.value && email.account_id !== selectedAccountId.value) return false
    if (email.direction !== directionFilter.value) return false
    if (linkFilter.value === 'linked' && !email.application_id) return false
    if (linkFilter.value === 'unlinked' && email.application_id) return false
    if (!normalized) return true
    return [email.subject, email.from_name, email.from_address]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(normalized))
  })
})

const directionCounts = computed(() => {
  const accountEmails = emails.value.filter(
    (email) => !selectedAccountId.value || email.account_id === selectedAccountId.value,
  )
  return {
    RECEIVED: accountEmails.filter((email) => email.direction === 'RECEIVED').length,
    SENT: accountEmails.filter((email) => email.direction === 'SENT').length,
  }
})

const selectedId = computed(() => Number(route.params.emailId) || null)
const missingFieldLabels = computed(() => {
  const fields = selectedEmail.value?.current_analysis?.missing_fields ?? []
  return [...new Set(fields.map(analysisFieldLabel))]
})
const emailHtmlDocument = computed(() => {
  const html = selectedEmail.value?.html_sanitized
  if (!html) return ''
  const remoteImageSources = externalImagesAllowed.value ? ' http: https:' : ''
  return `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8">
    <meta
      http-equiv="Content-Security-Policy"
      content="default-src 'none'; style-src 'unsafe-inline'; img-src data: blob:${remoteImageSources}; font-src 'none'; form-action 'none'; base-uri 'none'"
    >
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      :root { color-scheme: light; }
      html, body { min-height: 100%; margin: 0; background: #fff; }
      body {
        color: #25272b;
        font-family: Inter, "PingFang SC", "Microsoft YaHei", sans-serif;
        font-size: 14px;
        line-height: 1.75;
        overflow-wrap: anywhere;
      }
      img { max-width: 100%; height: auto; }
      img[data-jm-remote-src]:not([src]) { visibility: hidden; }
      table { max-width: 100%; }
      pre { white-space: pre-wrap; overflow-wrap: anywhere; }
    </style>
  </head>
  <body>${html}</body>
</html>`
})

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
    const routeEmail = emailRows.find((email) => email.id === routeId)
    if (routeEmail) directionFilter.value = routeEmail.direction
    const firstId =
      routeEmail
        ? routeId
        : filteredEmails.value[0]?.id
    if (firstId) await selectEmail(firstId, false)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    loadingList.value = false
  }
}

async function refreshEmailList() {
  if (loadingList.value || syncing.value) return
  try {
    emails.value = await emailApi.list()
    const routeEmail = emails.value.find((email) => email.id === selectedId.value)
    if (routeEmail) {
      directionFilter.value = routeEmail.direction
      return
    }
    if (!selectedEmail.value && filteredEmails.value[0]) {
      await selectEmail(filteredEmails.value[0].id, false)
    }
  } catch {
    // 轮询失败保持当前列表，手动同步仍会展示明确错误。
  }
}

function handleDataPoll() {
  void refreshEmailList()
}

function selectFirstFilteredEmail() {
  const first = filteredEmails.value[0]
  if (first) {
    void selectEmail(first.id)
    return
  }
  selectedEmail.value = null
  workflow.value = null
  void router.replace('/mail')
}

function setDirection(direction: 'RECEIVED' | 'SENT') {
  directionFilter.value = direction
  selectFirstFilteredEmail()
}

async function selectEmail(id: number, updateRoute = true) {
  if (loadingDetail.value) return
  loadingDetail.value = true
  workflow.value = null
  externalImagesAllowed.value = false
  externalImageCount.value = 0
  clearInlineImageUrls()
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

async function proposeEmailMove() {
  if (!selectedEmail.value) return
  movingEmail.value = true
  try {
    const restoring = selectedEmail.value.archive_status === 'ARCHIVED'
    const task = restoring
      ? await emailApi.proposeRestore(selectedEmail.value.id)
      : await emailApi.proposeArchive(selectedEmail.value.id)
    ElMessage.success(restoring ? '恢复申请已提交，等待审核' : '归档申请已提交，等待审核')
    await router.push(`/reviews/${task.id}`)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    movingEmail.value = false
  }
}

function closeMobileDetail() {
  selectedEmail.value = null
  workflow.value = null
  void router.replace('/mail')
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

function clearInlineImageUrls() {
  for (const url of inlineImageUrls) URL.revokeObjectURL(url)
  inlineImageUrls.clear()
}

async function handleEmailFrameLoad(event: Event) {
  const frame = event.currentTarget as HTMLIFrameElement
  const document = frame.contentDocument
  const email = selectedEmail.value
  if (!document || !email) return

  enhanceSanitizedEmailLinks(document)
  externalImageCount.value = countRemoteEmailImages(document)
  if (externalImagesAllowed.value) revealRemoteEmailImages(document)

  clearInlineImageUrls()
  const attachmentsByContentId = new Map(
    email.attachment_metadata
      .map((metadata, index) => [normalizeContentId(metadata.content_id), index] as const)
      .filter(([contentId]) => Boolean(contentId)),
  )
  await Promise.all(
    [...document.querySelectorAll<HTMLImageElement>('img[data-jm-cid]')].map(
      async (image) => {
        const index = attachmentsByContentId.get(normalizeContentId(image.dataset.jmCid))
        if (index === undefined) return
        try {
          const response = await emailApi.downloadAttachment(email.id, index)
          if (!response.data.type.startsWith('image/') || response.data.type === 'image/svg+xml') {
            return
          }
          if (selectedEmail.value?.id !== email.id || frame.contentDocument !== document) return
          const url = URL.createObjectURL(response.data)
          inlineImageUrls.add(url)
          image.src = url
        } catch {
          // 内嵌图片读取失败时保留替代文本，不影响邮件正文。
        }
      },
    ),
  )
}

watch(
  () => route.params.emailId,
  (value) => {
    const id = Number(value)
    if (id && id !== selectedEmail.value?.id) void selectEmail(id, false)
  },
)

onMounted(() => {
  window.addEventListener('job-mail:data-poll', handleDataPoll)
  void loadBaseData()
})
onUnmounted(() => {
  window.removeEventListener('job-mail:data-poll', handleDataPoll)
  clearInlineImageUrls()
})
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
            @change="selectFirstFilteredEmail"
          >
            <ElOption
              v-for="account in accounts"
              :key="account.id"
              :label="account.email_address"
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

        <div class="direction-tabs" role="tablist" aria-label="邮件方向">
          <button
            v-for="item in [
              { value: 'RECEIVED', label: '收件' },
              { value: 'SENT', label: '已发送' },
            ]"
            :key="item.value"
            type="button"
            :class="{ active: directionFilter === item.value }"
            @click="setDirection(item.value as 'RECEIVED' | 'SENT')"
          >
            {{ item.label }}
            <span>{{ directionCounts[item.value as 'RECEIVED' | 'SENT'] }}</span>
          </button>
        </div>

        <div class="search-row">
          <ElInput
            v-model="keyword"
            clearable
            :prefix-icon="Search"
            :placeholder="directionFilter === 'RECEIVED' ? '搜索收件' : '搜索已发送'"
          />
          <ElSelect
            v-model="linkFilter"
            class="link-filter"
            aria-label="关联状态"
            @change="selectFirstFilteredEmail"
          >
            <ElOption label="全部状态" value="all" />
            <ElOption label="已关联" value="linked" />
            <ElOption label="待关联" value="unlinked" />
          </ElSelect>
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
            <strong class="truncate">
              {{
                email.direction === 'SENT'
                  ? `发给 ${email.to_recipients.map(recipientText).join('，') || '未知收件人'}`
                  : email.from_name || email.from_address
              }}
            </strong>
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
            <p>
              {{
                directionFilter === 'SENT'
                  ? '当前已同步邮件中没有已发送记录'
                  : '没有符合条件的收件'
              }}
            </p>
            <span v-if="directionFilter === 'SENT' && accounts.length" class="quiet">
              这里显示由当前邮箱地址发出的邮件
            </span>
            <ElButton v-else-if="accounts.length" type="primary" plain @click="syncAccount">
              同步收件
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
          <ElButton
            class="mobile-back"
            text
            :icon="ArrowLeft"
            aria-label="返回邮件列表"
            @click="closeMobileDetail"
          >
            返回邮件列表
          </ElButton>
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
            <div class="ai-label"><span /> 智能分析</div>
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
            <div
              class="tab-scroll"
              :class="{ 'html-email-scroll': Boolean(selectedEmail.html_sanitized) }"
            >
              <div class="recipient-row">
                <span>收件人</span>
                <span>{{ selectedEmail.to_recipients.map(recipientText).join('，') || '—' }}</span>
              </div>
              <div
                v-if="externalImageCount > 0 && !externalImagesAllowed"
                class="external-image-notice"
              >
                <span>
                  该邮件包含 {{ externalImageCount }} 张外部图片，加载后可能会向发件人暴露已读状态。
                </span>
                <button type="button" @click="externalImagesAllowed = true">
                  显示外部图片
                </button>
              </div>
              <iframe
                v-if="selectedEmail.html_sanitized"
                class="email-frame"
                :srcdoc="emailHtmlDocument"
                title="邮件正文"
                sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
                referrerpolicy="no-referrer"
                @load="handleEmailFrameLoad"
              />
              <pre v-else class="email-plain">{{ selectedEmail.plain_body || '邮件正文为空' }}</pre>
            </div>
          </ElTabPane>

          <ElTabPane label="智能分析" name="analysis">
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
                    <span v-for="field in missingFieldLabels" :key="field">
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
                  <p>这封邮件还没有智能分析结果</p>
                  <span class="quiet">可使用页面底部的按钮开始处理</span>
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
              {{ workflowStatusLabels[workflow.status] || '状态未知' }}
            </span>
          </div>
          <span v-else />
          <div>
            <ElButton
              v-if="selectedEmail.archive_status !== 'PROPOSED'"
              :icon="selectedEmail.archive_status === 'ARCHIVED' ? RefreshLeft : TakeawayBox"
              :loading="movingEmail"
              @click="proposeEmailMove"
            >
              {{ selectedEmail.archive_status === 'ARCHIVED' ? '恢复邮件' : '归档邮件' }}
            </ElButton>
            <ElButton v-else disabled>归档待审核</ElButton>
            <ElButton
              v-if="workflow?.pending_review_task_id"
              type="primary"
              plain
              @click="openReview"
            >
              前往审核
            </ElButton>
            <ElButton
              v-if="!workflow?.pending_review_task_id"
              type="primary"
              :loading="processing"
              @click="startWorkflow"
            >
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
  grid-template-columns: clamp(360px, 32%, 520px) minmax(0, 1fr);
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
  min-width: 0;
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

.direction-tabs {
  display: flex;
  gap: 6px;
  padding: 3px;
  background: #f1f3f5;
  border-radius: 7px;
}

.direction-tabs button {
  display: flex;
  min-width: 0;
  flex: 1;
  gap: 7px;
  align-items: center;
  justify-content: center;
  padding: 7px 10px;
  color: var(--jm-text-secondary);
  font-size: 13px;
  background: transparent;
  border: 0;
  border-radius: 5px;
  cursor: pointer;
}

.direction-tabs button:hover {
  color: #245bdb;
}

.direction-tabs button.active {
  color: #245bdb;
  font-weight: 500;
  background: #fff;
  box-shadow: 0 1px 3px rgb(31 35 41 / 10%);
}

.direction-tabs span {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  color: var(--jm-text-tertiary);
  font-size: 10px;
  line-height: 18px;
  background: rgb(143 149 158 / 12%);
  border-radius: 9px;
}

.direction-tabs button.active span {
  color: #245bdb;
  background: var(--jm-primary-soft);
}

.search-row {
  display: flex;
  gap: 8px;
}

.search-row > .el-input {
  min-width: 0;
  flex: 1;
}

.link-filter {
  width: 108px;
  flex: 0 0 108px;
}

.mail-list {
  min-width: 0;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
}

.mail-row {
  display: grid;
  box-sizing: border-box;
  min-width: 0;
  width: 100%;
  gap: 7px;
  padding: 14px 16px;
  overflow: hidden;
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
  min-width: 0;
  gap: 10px;
  align-items: baseline;
  justify-content: space-between;
}

.mail-row-head strong {
  min-width: 0;
  flex: 1;
  font-size: 14px;
}

.mail-row-head time {
  flex: 0 0 auto;
  color: var(--jm-text-tertiary);
  font-size: 11px;
}

.mail-subject {
  min-width: 0;
  max-width: 100%;
  font-size: 13px;
  color: var(--jm-text-secondary);
}

.mail-meta {
  display: flex;
  min-width: 0;
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
  min-width: 0;
  padding: 20px 24px 0;
  overflow: hidden;
}

.mobile-back {
  display: none;
}

.detail-title h2 {
  margin: 0 0 16px;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.sender-line {
  display: flex;
  min-width: 0;
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
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sender-line span {
  overflow: hidden;
  color: var(--jm-text-tertiary);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sender-line time {
  flex: 0 0 auto;
  margin-left: auto;
  color: var(--jm-text-tertiary);
  font-size: 12px;
  white-space: nowrap;
}

.analysis-strip {
  display: flex;
  min-width: 0;
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
  overflow: hidden;
  color: var(--jm-text-secondary);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.analysis-strip p.truncate {
  display: -webkit-box;
  white-space: normal;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
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
  min-width: 0;
  min-height: 0;
  margin-top: 6px;
  overflow: hidden;
}

.detail-tabs :deep(.el-tabs__header) {
  margin: 0;
  padding: 0 24px;
}

.detail-tabs :deep(.el-tabs__content),
.detail-tabs :deep(.el-tab-pane) {
  min-width: 0;
  height: 100%;
  min-height: 0;
}

.detail-tabs :deep(.el-tabs__content) {
  height: calc(100% - 40px);
}

.tab-scroll {
  box-sizing: border-box;
  min-width: 0;
  width: 100%;
  height: 100%;
  padding: 20px 24px;
  overflow-x: hidden;
  overflow-y: auto;
}

.html-email-scroll {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.recipient-row {
  display: flex;
  min-width: 0;
  gap: 14px;
  margin-bottom: 18px;
  padding-bottom: 12px;
  color: var(--jm-text-secondary);
  font-size: 12px;
  border-bottom: 1px solid var(--jm-border-light);
}

.recipient-row span:first-child {
  flex: 0 0 auto;
  color: var(--jm-text-tertiary);
}

.recipient-row span:last-child {
  min-width: 0;
  overflow-wrap: anywhere;
}

.external-image-notice {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
  margin: -4px 0 14px;
  padding: 10px 12px;
  color: #6b4f18;
  font-size: 12px;
  background: #fff8e8;
  border: 1px solid #f2ddb0;
  border-radius: 6px;
}

.external-image-notice button {
  flex: 0 0 auto;
  padding: 0;
  color: #245bdb;
  font: inherit;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.external-image-notice button:hover {
  text-decoration: underline;
}

.email-frame {
  display: block;
  min-width: 0;
  width: 100%;
  min-height: 0;
  flex: 1;
  background: #fff;
  border: 0;
}

.email-plain {
  box-sizing: border-box;
  min-width: 0;
  width: 100%;
  max-width: 100%;
  margin: 0;
  color: #25272b;
  font: inherit;
  font-size: 14px;
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.analysis-content {
  width: 100%;
  max-width: 960px;
}

.mail-list > .empty-state > div {
  display: grid;
  gap: 12px;
  justify-items: center;
  text-align: center;
}

.mail-list > .empty-state p {
  margin: 0;
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

  .detail-header {
    padding-top: 12px;
  }

  .mobile-back {
    display: inline-flex;
    margin: 0 0 10px -10px;
  }
}
</style>
