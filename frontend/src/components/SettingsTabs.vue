<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const tabs = [
  { path: '/settings/mailboxes', label: '邮箱账户' },
  { path: '/settings/llm', label: 'AI 模型' },
]

function navigate(path: string) {
  void router.push(path)
}
</script>

<template>
  <nav class="settings-tabs" aria-label="设置分区">
    <button
      v-for="tab in tabs"
      :key="tab.path"
      type="button"
      class="settings-tab"
      :class="{ active: route.path === tab.path }"
      @click="navigate(tab.path)"
    >
      {{ tab.label }}
    </button>
  </nav>
</template>

<style scoped>
.settings-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 20px;
  padding: 4px;
  background: #f1f3f5;
  border-radius: 8px;
}

.settings-tab {
  padding: 7px 18px;
  color: var(--jm-text-secondary);
  font-size: 13px;
  background: transparent;
  border: 0;
  border-radius: 6px;
  cursor: pointer;
}

.settings-tab:hover {
  color: var(--jm-text);
}

.settings-tab.active {
  color: #245bdb;
  font-weight: 600;
  background: #fff;
  box-shadow: 0 1px 3px rgb(15 23 42 / 10%);
}
</style>
