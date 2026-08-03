<script setup lang="ts">
import {
  CircleCheck,
  CircleClose,
  Connection,
  Delete,
  Edit,
  Key,
  Link,
  Plus,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { llmConfigApi } from '@/api'
import { getApiErrorMessage } from '@/api/http'
import SettingsTabs from '@/components/SettingsTabs.vue'
import type { LlmConfig, LlmConfigCreate, LlmConfigTestResult } from '@/types/api'

const API_KEY_GUIDE_URL = 'https://platform.deepseek.com/api_keys'

const configs = ref<LlmConfig[]>([])
const loading = ref(false)
const saving = ref(false)
const testingId = ref<number | null>(null)
const activatingId = ref<number | null>(null)
const dialogVisible = ref(false)
const editing = ref<LlmConfig | null>(null)
const advancedVisible = ref(false)
const formRef = ref<FormInstance>()
const testVisible = ref(false)
const testResult = ref<LlmConfigTestResult | null>(null)

const form = reactive<LlmConfigCreate>({
  model: 'deepseek-chat',
  api_key: '',
  base_url: '',
  temperature: 0,
  timeout_seconds: 60,
  max_retries: 2,
  is_active: false,
})

const rules: FormRules = {
  model: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
  api_key: [
    {
      validator: (_rule, value, callback) => {
        if (!editing.value && !value) {
          callback(new Error('请输入 DeepSeek API Key'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

function openCreateDialog() {
  editing.value = null
  Object.assign(form, {
    model: 'deepseek-chat',
    api_key: '',
    base_url: '',
    temperature: 0,
    timeout_seconds: 60,
    max_retries: 2,
    is_active: !configs.value.some((config) => config.is_active),
  })
  advancedVisible.value = false
  dialogVisible.value = true
}

function openEditDialog(config: LlmConfig) {
  editing.value = config
  Object.assign(form, {
    model: config.model,
    api_key: '',
    base_url: config.base_url ?? '',
    temperature: config.temperature,
    timeout_seconds: config.timeout_seconds,
    max_retries: config.max_retries,
    is_active: config.is_active,
  })
  advancedVisible.value = false
  dialogVisible.value = true
}

async function loadConfigs() {
  loading.value = true
  try {
    configs.value = await llmConfigApi.list()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  if (!(await formRef.value?.validate())) return
  saving.value = true
  try {
    let saved: LlmConfig
    if (editing.value) {
      saved = await llmConfigApi.update(editing.value.id, {
        model: form.model,
        api_key: form.api_key || undefined,
        base_url: form.base_url || null,
        temperature: form.temperature,
        timeout_seconds: form.timeout_seconds,
        max_retries: form.max_retries,
      })
      ElMessage.success('AI 配置已更新，正在测试连接')
    } else {
      saved = await llmConfigApi.create({
        model: form.model,
        api_key: form.api_key || undefined,
        base_url: form.base_url || null,
        temperature: form.temperature,
        timeout_seconds: form.timeout_seconds,
        max_retries: form.max_retries,
        is_active: form.is_active,
      })
      ElMessage.success('AI 配置已保存，正在测试连接')
    }
    dialogVisible.value = false
    await loadConfigs()
    testResult.value = await llmConfigApi.test(saved.id, form.api_key || undefined)
    testVisible.value = true
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    saving.value = false
  }
}

async function testConfig(config: LlmConfig, apiKeyOverride?: string) {
  testingId.value = config.id
  try {
    testResult.value = await llmConfigApi.test(config.id, apiKeyOverride)
    testVisible.value = true
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    testingId.value = null
  }
}

async function setActive(config: LlmConfig, value: boolean) {
  activatingId.value = config.id
  try {
    await llmConfigApi.setActive(config.id, value)
    ElMessage.success(value ? '已切换为当前启用配置' : '该配置已停用')
    await loadConfigs()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
    await loadConfigs()
  } finally {
    activatingId.value = null
  }
}

async function deleteConfig(config: LlmConfig) {
  try {
    await ElMessageBox.confirm(
      `确定删除配置「${config.model}」吗？删除后无法恢复。`,
      '删除 AI 配置',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await llmConfigApi.remove(config.id)
    ElMessage.success('配置已删除')
    await loadConfigs()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

onMounted(() => {
  void loadConfigs()
})
</script>

<template>
  <div class="page-shell settings-page">
    <SettingsTabs />

    <div class="settings-intro">
      <div>
        <h2>AI 模型配置</h2>
        <p>系统使用 DeepSeek 大模型分析求职邮件、匹配申请进度并起草回复。</p>
      </div>
      <ElButton type="primary" :icon="Plus" @click="openCreateDialog">添加配置</ElButton>
    </div>

    <section v-loading="loading" class="config-list">
      <article v-for="config in configs" :key="config.id" class="surface config-card">
        <div class="config-head">
          <div class="provider-mark">DS</div>
          <div>
            <h3>{{ config.model }}</h3>
            <span>DeepSeek 开放平台</span>
          </div>
          <div class="config-active">
            <span>{{ config.is_active ? '当前启用' : '未启用' }}</span>
            <ElSwitch
              :model-value="config.is_active"
              :loading="activatingId === config.id"
              @change="setActive(config, Boolean($event))"
            />
          </div>
        </div>

        <dl class="config-grid">
          <div>
            <dt>API Key</dt>
            <dd :class="{ unset: !config.api_key_configured }">
              {{ config.api_key_configured ? '已配置' : '未配置' }}
            </dd>
            <span>加密存储，页面不回显</span>
          </div>
          <div>
            <dt>温度</dt>
            <dd>{{ config.temperature }}</dd>
            <span>输出随机性</span>
          </div>
          <div>
            <dt>超时</dt>
            <dd>{{ config.timeout_seconds }} 秒</dd>
            <span>单次请求</span>
          </div>
          <div>
            <dt>重试</dt>
            <dd>{{ config.max_retries }} 次</dd>
            <span>失败自动重试</span>
          </div>
        </dl>

        <div class="config-actions">
          <ElButton
            :icon="Connection"
            :disabled="!config.api_key_configured"
            :loading="testingId === config.id"
            @click="testConfig(config)"
          >
            测试连接
          </ElButton>
          <ElButton :icon="Edit" @click="openEditDialog(config)">编辑</ElButton>
          <ElButton :icon="Delete" :disabled="config.is_active" @click="deleteConfig(config)">
            删除
          </ElButton>
        </div>
      </article>

      <div v-if="!loading && configs.length === 0" class="surface config-empty">
        <div class="empty-mark">AI</div>
        <h3>还没有 AI 模型配置</h3>
        <p>跟随指引在 DeepSeek 开放平台创建 API Key，粘贴到这里即可开始使用。</p>
        <ElButton type="primary" @click="openCreateDialog">添加配置</ElButton>
      </div>
    </section>

    <ElDialog v-model="dialogVisible" title="添加配置" width="min(680px, 94vw)">
      <ElForm ref="formRef" :model="form" :rules="rules" label-position="top">
        <section class="provider-guide">
          <div class="guide-heading">
            <div class="guide-key"><ElIcon><Key /></ElIcon></div>
            <div>
              <h4>获取 DeepSeek API Key</h4>
              <p>DeepSeek 的 API Key 需在其开放平台创建。</p>
            </div>
            <ElLink
              :href="API_KEY_GUIDE_URL"
              target="_blank"
              rel="noopener noreferrer"
              type="primary"
            >
              打开 DeepSeek 开放平台
              <ElIcon><Link /></ElIcon>
            </ElLink>
          </div>
          <ol>
            <li>登录 DeepSeek 开放平台（platform.deepseek.com），进入「API Keys」页面。</li>
            <li>点击「创建 API Key」，填写名称后复制生成的 Key。Key 只会完整显示一次。</li>
            <li>将复制的 Key 粘贴到下方输入框。账户需要预先充值才能正常调用。</li>
          </ol>
        </section>

        <ElFormItem label="模型名称" prop="model">
          <ElInput v-model="form.model" placeholder="deepseek-chat" />
          <p class="field-hint">填「deepseek-chat」使用通用对话模型，或「deepseek-reasoner」使用推理模型。</p>
        </ElFormItem>

        <ElFormItem label="API Key" prop="api_key">
          <ElInput
            v-model="form.api_key"
            type="password"
            show-password
            autocomplete="new-password"
            :placeholder="editing ? '留空表示保留原有 Key' : '粘贴刚创建的 API Key'"
          />
          <p class="field-hint">形如 sk-xxxxxxxxxxxxxxxx，由 DeepSeek 开放平台生成。</p>
        </ElFormItem>

        <ElFormItem>
          <ElCheckbox v-model="form.is_active">
            保存后设为当前启用配置（会停用其他配置）
          </ElCheckbox>
        </ElFormItem>

        <ElButton text type="primary" class="advanced-toggle" @click="advancedVisible = !advancedVisible">
          {{ advancedVisible ? '收起高级设置' : '展开高级设置' }}
        </ElButton>

        <div v-if="advancedVisible" class="advanced-grid">
          <ElFormItem label="Base URL（可选）">
            <ElInput v-model="form.base_url" placeholder="留空使用 DeepSeek 默认地址" />
          </ElFormItem>
          <ElFormItem label="温度（0-2）">
            <ElInputNumber
              v-model="form.temperature"
              :min="0"
              :max="2"
              :step="0.1"
              controls-position="right"
            />
          </ElFormItem>
          <ElFormItem label="超时（秒）">
            <ElInputNumber
              v-model="form.timeout_seconds"
              :min="5"
              :max="600"
              controls-position="right"
            />
          </ElFormItem>
          <ElFormItem label="失败重试次数">
            <ElInputNumber v-model="form.max_retries" :min="0" :max="10" controls-position="right" />
          </ElFormItem>
        </div>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="saving" @click="saveConfig">保存</ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="testVisible" title="连接测试结果" width="min(460px, 92vw)">
      <div v-if="testResult" class="test-result">
        <div :class="{ success: testResult.success, failed: !testResult.success }">
          <ElIcon :size="22">
            <component :is="testResult.success ? CircleCheck : CircleClose" />
          </ElIcon>
          <div>
            <strong>{{ testResult.success ? '连接成功' : '连接失败' }}</strong>
            <span>{{ testResult.message }}</span>
            <span v-if="testResult.latency_ms !== null" class="latency">
              响应耗时 {{ testResult.latency_ms }} ms
            </span>
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

.config-list {
  display: grid;
  gap: 14px;
}

.config-card {
  padding: 20px;
}

.config-head {
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

.config-head > div:nth-child(2) {
  display: grid;
  gap: 3px;
}

.config-head h3 {
  margin: 0;
  font-size: 14px;
}

.config-head span {
  color: var(--jm-text-tertiary);
  font-size: 11px;
}

.config-active {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-left: auto;
  color: var(--jm-text-secondary);
  font-size: 11px;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin: 18px 0;
  border: 1px solid var(--jm-border-light);
  border-radius: 7px;
  overflow: hidden;
}

.config-grid > div {
  display: grid;
  min-width: 0;
  gap: 4px;
  padding: 12px 14px;
  border-right: 1px solid var(--jm-border-light);
}

.config-grid > div:last-child {
  border-right: 0;
}

.config-grid dt {
  color: var(--jm-text-tertiary);
  font-size: 11px;
}

.config-grid dd {
  margin: 0;
  font-size: 12px;
}

.config-grid dd.unset {
  color: var(--jm-warning);
}

.config-grid span {
  color: var(--jm-text-tertiary);
  font-size: 10px;
}

.config-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.config-empty {
  padding: 60px 20px;
  text-align: center;
}

.empty-mark {
  display: grid;
  width: 44px;
  height: 44px;
  margin: 0 auto 12px;
  color: var(--jm-primary);
  font-size: 15px;
  font-weight: 700;
  background: var(--jm-primary-soft);
  border-radius: 10px;
  place-items: center;
}

.config-empty h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.config-empty p {
  max-width: 420px;
  margin: 0 auto 18px;
  color: var(--jm-text-secondary);
  font-size: 12px;
}

.provider-guide {
  margin-bottom: 16px;
  padding: 16px;
  background: #f3f7ff;
  border: 1px solid #dce7fb;
  border-radius: 9px;
}

.guide-heading {
  display: flex;
  gap: 11px;
  align-items: flex-start;
}

.guide-key {
  display: grid;
  flex: 0 0 auto;
  width: 32px;
  height: 32px;
  color: var(--jm-primary);
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgb(36 91 219 / 12%);
  place-items: center;
}

.guide-heading > div:nth-child(2) {
  min-width: 0;
  margin-right: auto;
}

.guide-heading h4 {
  margin: 0 0 3px;
  font-size: 13px;
}

.guide-heading p {
  margin: 0;
  color: var(--jm-text-secondary);
  font-size: 11px;
  line-height: 1.5;
}

.guide-heading :deep(.el-link) {
  flex: 0 0 auto;
  gap: 4px;
  font-size: 11px;
}

.provider-guide ol {
  display: grid;
  gap: 7px;
  margin: 13px 0 0 43px;
  padding: 0;
  color: var(--jm-text-secondary);
  font-size: 11px;
  line-height: 1.55;
}

.field-hint {
  margin: 5px 0 0;
  color: var(--jm-text-tertiary);
  font-size: 11px;
}

.advanced-toggle {
  margin: 0 0 10px;
  padding-left: 0;
}

.advanced-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 14px;
  padding: 14px;
  background: #f8f9fa;
  border-radius: 7px;
}

.advanced-grid :deep(.el-input-number),
.advanced-grid :deep(.el-select) {
  width: 100%;
}

.test-result {
  display: grid;
  gap: 10px;
}

.test-result > div {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 13px;
  border-radius: 7px;
}

.test-result .success {
  color: #24714e;
  background: #eef8f3;
}

.test-result .failed {
  color: #a33832;
  background: #fff0ef;
}

.test-result > div > div {
  display: grid;
  gap: 3px;
}

.test-result strong {
  font-size: 13px;
}

.test-result span {
  font-size: 11px;
}

.test-result .latency {
  color: var(--jm-text-tertiary);
}

@media (max-width: 640px) {
  .config-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .config-grid > div:nth-child(2) {
    border-right: 0;
  }

  .config-grid > div:nth-child(-n + 2) {
    border-bottom: 1px solid var(--jm-border-light);
  }

  .advanced-grid {
    grid-template-columns: 1fr;
  }

  .guide-heading {
    align-items: stretch;
    flex-direction: column;
  }

  .provider-guide ol {
    margin-left: 20px;
  }
}
</style>
