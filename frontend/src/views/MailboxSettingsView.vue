<script setup lang="ts">
import { CircleCheck, CircleClose, Connection, Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { emailAccountApi } from '@/api'
import { getApiErrorMessage } from '@/api/http'
import { formatDateTime } from '@/utils/format'
import type {
  EmailAccount,
  EmailAccountCreate,
  EmailConnectionTestResult,
} from '@/types/api'

const accounts = ref<EmailAccount[]>([])
const loading = ref(false)
const createVisible = ref(false)
const creating = ref(false)
const testingId = ref<number | null>(null)
const syncingId = ref<number | null>(null)
const testVisible = ref(false)
const testResult = ref<EmailConnectionTestResult | null>(null)
const formRef = ref<FormInstance>()

const form = reactive<EmailAccountCreate>({
  provider: '163',
  email_address: '',
  imap_host: 'imap.163.com',
  imap_port: 993,
  imap_security: 'SSL',
  smtp_host: 'smtp.163.com',
  smtp_port: 465,
  smtp_security: 'SSL',
  credential_ref: 'JOB_MAIL_EMAIL_AUTH_CODE',
  is_active: true,
})

const rules: FormRules = {
  email_address: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '邮箱地址格式不正确', trigger: 'blur' },
  ],
  imap_host: [{ required: true, message: '请输入 IMAP 主机', trigger: 'blur' }],
  smtp_host: [{ required: true, message: '请输入 SMTP 主机', trigger: 'blur' }],
  credential_ref: [
    { required: true, message: '请输入授权码环境变量名', trigger: 'blur' },
    {
      pattern: /^[A-Z][A-Z0-9_]+$/,
      message: '仅支持大写字母、数字和下划线，且必须以字母开头',
      trigger: 'blur',
    },
  ],
}

async function loadAccounts() {
  loading.value = true
  try {
    accounts.value = await emailAccountApi.list()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function createAccount() {
  if (!(await formRef.value?.validate())) return
  creating.value = true
  try {
    await emailAccountApi.create(form)
    ElMessage.success('邮箱账户已添加')
    createVisible.value = false
    await loadAccounts()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    creating.value = false
  }
}

async function testConnection(account: EmailAccount) {
  testingId.value = account.id
  try {
    testResult.value = await emailAccountApi.test(account.id)
    testVisible.value = true
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    testingId.value = null
  }
}

async function syncAccount(account: EmailAccount) {
  syncingId.value = account.id
  try {
    const result = await emailAccountApi.sync(account.id)
    ElMessage.success(`同步完成，新增 ${result.created} 封，跳过 ${result.skipped} 封`)
    await loadAccounts()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    syncingId.value = null
  }
}

onMounted(loadAccounts)
</script>

<template>
  <div class="page-shell settings-page">
    <div class="settings-intro">
      <div>
        <h2>邮箱账户</h2>
        <p>系统通过 IMAP 只读同步收件箱，通过 SMTP 发送经你确认的回复。</p>
      </div>
      <ElButton type="primary" :icon="Plus" @click="createVisible = true">添加邮箱</ElButton>
    </div>

    <section v-loading="loading" class="account-list">
      <article v-for="account in accounts" :key="account.id" class="surface account-card">
        <div class="account-head">
          <div class="provider-mark">{{ account.provider.slice(0, 2).toUpperCase() }}</div>
          <div>
            <h3>{{ account.email_address_masked }}</h3>
            <span>{{ account.provider }} 邮箱</span>
          </div>
          <ElTag :type="account.is_active ? 'success' : 'info'" effect="light">
            {{ account.is_active ? '已启用' : '未启用' }}
          </ElTag>
        </div>

        <dl class="connection-grid">
          <div>
            <dt>IMAP</dt>
            <dd>{{ account.imap_host }}:{{ account.imap_port }}</dd>
            <span>{{ account.imap_security }}</span>
          </div>
          <div>
            <dt>SMTP</dt>
            <dd>{{ account.smtp_host }}:{{ account.smtp_port }}</dd>
            <span>{{ account.smtp_security }}</span>
          </div>
          <div>
            <dt>最近同步</dt>
            <dd>{{ formatDateTime(account.last_sync_at) }}</dd>
            <span v-if="account.last_synced_uid">最新 UID {{ account.last_synced_uid }}</span>
            <span v-else>尚未同步</span>
          </div>
          <div>
            <dt>同步状态</dt>
            <dd :class="{ error: account.last_sync_status === 'FAILED' }">
              {{ account.last_sync_status || '未运行' }}
            </dd>
            <span class="truncate">{{ account.last_sync_error || `UIDVALIDITY ${account.inbox_uid_validity ?? '—'}` }}</span>
          </div>
        </dl>

        <div class="account-actions">
          <ElButton
            :icon="Connection"
            :loading="testingId === account.id"
            @click="testConnection(account)"
          >
            测试连接
          </ElButton>
          <ElButton
            type="primary"
            plain
            :icon="Refresh"
            :loading="syncingId === account.id"
            @click="syncAccount(account)"
          >
            同步收件箱
          </ElButton>
        </div>
      </article>

      <div v-if="!loading && accounts.length === 0" class="surface account-empty">
        <div class="empty-mail-mark">@</div>
        <h3>还没有邮箱账户</h3>
        <p>添加用于毕业设计演示的 163 测试邮箱，授权码从后端环境变量读取。</p>
        <ElButton type="primary" @click="createVisible = true">添加邮箱</ElButton>
      </div>
    </section>

    <aside class="security-note">
      <strong>凭据安全</strong>
      <p>
        页面不会读取或显示邮箱授权码。请在后端环境变量中配置授权码，并只在这里填写对应的环境变量名称。
      </p>
    </aside>

    <ElDialog v-model="createVisible" title="添加邮箱账户" width="min(640px, 94vw)">
      <ElForm ref="formRef" :model="form" :rules="rules" label-position="top">
        <div class="form-grid">
          <ElFormItem label="邮箱服务商">
            <ElSelect v-model="form.provider">
              <ElOption label="163 邮箱" value="163" />
            </ElSelect>
          </ElFormItem>
          <ElFormItem label="邮箱地址" prop="email_address">
            <ElInput v-model="form.email_address" placeholder="example@163.com" />
          </ElFormItem>
        </div>

        <div class="protocol-section">
          <h4>接收邮件（IMAP）</h4>
          <div class="protocol-grid">
            <ElFormItem label="服务器" prop="imap_host">
              <ElInput v-model="form.imap_host" />
            </ElFormItem>
            <ElFormItem label="端口">
              <ElInputNumber v-model="form.imap_port" :min="1" :max="65535" controls-position="right" />
            </ElFormItem>
            <ElFormItem label="安全方式">
              <ElSelect v-model="form.imap_security">
                <ElOption label="SSL" value="SSL" />
                <ElOption label="STARTTLS" value="STARTTLS" />
              </ElSelect>
            </ElFormItem>
          </div>
        </div>

        <div class="protocol-section">
          <h4>发送邮件（SMTP）</h4>
          <div class="protocol-grid">
            <ElFormItem label="服务器" prop="smtp_host">
              <ElInput v-model="form.smtp_host" />
            </ElFormItem>
            <ElFormItem label="端口">
              <ElInputNumber v-model="form.smtp_port" :min="1" :max="65535" controls-position="right" />
            </ElFormItem>
            <ElFormItem label="安全方式">
              <ElSelect v-model="form.smtp_security">
                <ElOption label="SSL" value="SSL" />
                <ElOption label="STARTTLS" value="STARTTLS" />
              </ElSelect>
            </ElFormItem>
          </div>
        </div>

        <ElFormItem label="授权码环境变量名" prop="credential_ref">
          <ElInput v-model="form.credential_ref" />
          <p class="field-hint">这里只保存变量名称，不保存授权码本身。</p>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="createVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="creating" @click="createAccount">添加邮箱</ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="testVisible" title="连接测试结果" width="min(460px, 92vw)">
      <div v-if="testResult" class="test-results">
        <div :class="{ success: testResult.imap.success, failed: !testResult.imap.success }">
          <ElIcon :size="22">
            <component :is="testResult.imap.success ? CircleCheck : CircleClose" />
          </ElIcon>
          <div>
            <strong>IMAP 接收连接</strong>
            <span>{{ testResult.imap.message }}</span>
          </div>
        </div>
        <div :class="{ success: testResult.smtp.success, failed: !testResult.smtp.success }">
          <ElIcon :size="22">
            <component :is="testResult.smtp.success ? CircleCheck : CircleClose" />
          </ElIcon>
          <div>
            <strong>SMTP 发送连接</strong>
            <span>{{ testResult.smtp.message }}</span>
          </div>
        </div>
      </div>
      <template #footer>
        <ElButton type="primary" @click="testVisible = false">完成</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 980px;
  margin: 0 auto;
}

.settings-intro {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 20px;
}

.settings-intro h2 {
  margin: 0 0 6px;
  font-size: 17px;
}

.settings-intro p {
  margin: 0;
  color: var(--jm-text-secondary);
  font-size: 13px;
}

.account-list {
  display: grid;
  gap: 14px;
}

.account-card {
  padding: 20px;
}

.account-head {
  display: flex;
  gap: 12px;
  align-items: center;
}

.provider-mark {
  display: grid;
  width: 38px;
  height: 38px;
  color: #245bdb;
  font-size: 12px;
  font-weight: 700;
  background: var(--jm-primary-soft);
  border-radius: 8px;
  place-items: center;
}

.account-head > div:nth-child(2) {
  display: grid;
  gap: 3px;
}

.account-head h3 {
  margin: 0;
  font-size: 14px;
}

.account-head span {
  color: var(--jm-text-tertiary);
  font-size: 11px;
}

.account-head .el-tag {
  margin-left: auto;
}

.connection-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin: 18px 0;
  border: 1px solid var(--jm-border-light);
  border-radius: 7px;
  overflow: hidden;
}

.connection-grid > div {
  display: grid;
  min-width: 0;
  gap: 4px;
  padding: 12px 14px;
  border-right: 1px solid var(--jm-border-light);
}

.connection-grid > div:last-child {
  border-right: 0;
}

.connection-grid dt {
  color: var(--jm-text-tertiary);
  font-size: 11px;
}

.connection-grid dd {
  margin: 0;
  font-size: 12px;
}

.connection-grid dd.error {
  color: var(--jm-danger);
}

.connection-grid span {
  color: var(--jm-text-tertiary);
  font-size: 10px;
}

.account-actions {
  display: flex;
  justify-content: flex-end;
}

.account-empty {
  padding: 60px 20px;
  text-align: center;
}

.empty-mail-mark {
  display: grid;
  width: 44px;
  height: 44px;
  margin: 0 auto 12px;
  color: var(--jm-primary);
  font-size: 22px;
  background: var(--jm-primary-soft);
  border-radius: 10px;
  place-items: center;
}

.account-empty h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.account-empty p {
  max-width: 420px;
  margin: 0 auto 18px;
  color: var(--jm-text-secondary);
  font-size: 12px;
}

.security-note {
  margin-top: 14px;
  padding: 13px 15px;
  color: var(--jm-text-secondary);
  background: #eef3f5;
  border-radius: 7px;
}

.security-note strong {
  font-size: 12px;
}

.security-note p {
  margin: 4px 0 0;
  font-size: 11px;
  line-height: 1.6;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 14px;
}

.protocol-section {
  margin-bottom: 18px;
  padding: 14px;
  background: #f8f9fa;
  border-radius: 7px;
}

.protocol-section h4 {
  margin: 0 0 12px;
  font-size: 13px;
}

.protocol-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(110px, 0.7fr) minmax(120px, 0.8fr);
  gap: 12px;
}

.protocol-grid :deep(.el-form-item) {
  margin-bottom: 0;
}

.protocol-grid :deep(.el-input-number),
.protocol-grid :deep(.el-select),
.form-grid :deep(.el-select) {
  width: 100%;
}

.field-hint {
  margin: 5px 0 0;
  color: var(--jm-text-tertiary);
  font-size: 11px;
}

.test-results {
  display: grid;
  gap: 10px;
}

.test-results > div {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 13px;
  border-radius: 7px;
}

.test-results .success {
  color: #24714e;
  background: #eef8f3;
}

.test-results .failed {
  color: #a33832;
  background: #fff0ef;
}

.test-results > div > div {
  display: grid;
  gap: 3px;
}

.test-results strong {
  font-size: 13px;
}

.test-results span {
  font-size: 11px;
}

@media (max-width: 760px) {
  .connection-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .connection-grid > div:nth-child(2) {
    border-right: 0;
  }

  .connection-grid > div:nth-child(-n + 2) {
    border-bottom: 1px solid var(--jm-border-light);
  }
}

@media (max-width: 560px) {
  .form-grid,
  .protocol-grid {
    grid-template-columns: 1fr;
  }

  .protocol-grid :deep(.el-form-item) {
    margin-bottom: 12px;
  }
}
</style>
