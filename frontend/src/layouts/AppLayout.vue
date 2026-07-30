<script setup lang="ts">
import {
  Calendar,
  Checked,
  Expand,
  Fold,
  Message,
  Setting,
  Tickets,
} from '@element-plus/icons-vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { reminderApi, reviewApi } from '@/api'

const route = useRoute()
const router = useRouter()
const collapsed = ref(false)
const pendingCount = ref(0)
const reminderCount = ref(0)
let pollTimer: number | undefined

interface NavItem {
  path: string
  label: string
  icon: Component
  badge?: number
}

const navItems = computed<NavItem[]>(() => [
  { path: '/mail', label: '邮件', icon: Message },
  { path: '/applications', label: '求职进度', icon: Tickets },
  { path: '/calendar', label: '日程', icon: Calendar },
  { path: '/reviews', label: '审核', icon: Checked, badge: pendingCount.value },
])

const activePath = computed(() => {
  if (route.path.startsWith('/mail')) return '/mail'
  if (route.path.startsWith('/applications')) return '/applications'
  if (route.path.startsWith('/calendar')) return '/calendar'
  if (route.path.startsWith('/reviews')) return '/reviews'
  return '/settings/mailboxes'
})

const pageTitle = computed(() => String(route.meta.title ?? '求职邮迹'))

async function loadPendingCount() {
  try {
    const [tasks, reminders] = await Promise.all([
      reviewApi.list(),
      reminderApi.list(true),
    ])
    pendingCount.value = tasks.filter((task) => task.status === 'PENDING').length
    reminderCount.value = reminders.length
  } catch {
    pendingCount.value = 0
    reminderCount.value = 0
  }
}

function navigate(path: string) {
  void router.push(path)
}

watch(
  () => route.fullPath,
  () => void loadPendingCount(),
)

onMounted(() => {
  void loadPendingCount()
  pollTimer = window.setInterval(loadPendingCount, 20_000)
})

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer)
})
</script>

<template>
  <div class="app-layout" :class="{ 'is-collapsed': collapsed }">
    <aside class="app-sidebar">
      <div class="brand" :title="collapsed ? '求职邮迹' : undefined">
        <div class="brand-mark" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <div v-if="!collapsed" class="brand-copy">
          <strong>求职邮迹</strong>
          <small>求职邮件助手</small>
        </div>
      </div>

      <nav class="app-nav" aria-label="主导航">
        <button
          v-for="item in navItems"
          :key="item.path"
          class="nav-item"
          :class="{ active: activePath === item.path }"
          :title="collapsed ? item.label : undefined"
          type="button"
          @click="navigate(item.path)"
        >
          <ElIcon :size="18"><component :is="item.icon" /></ElIcon>
          <span v-if="!collapsed">{{ item.label }}</span>
          <span v-if="item.badge && item.badge > 0" class="nav-badge">{{ item.badge }}</span>
        </button>
      </nav>

      <div class="sidebar-footer">
        <button
          class="nav-item"
          :class="{ active: activePath === '/settings/mailboxes' }"
          :title="collapsed ? '邮箱设置' : undefined"
          type="button"
          @click="navigate('/settings/mailboxes')"
        >
          <ElIcon :size="18"><Setting /></ElIcon>
          <span v-if="!collapsed">邮箱设置</span>
        </button>
        <button
          class="collapse-button"
          type="button"
          :aria-label="collapsed ? '展开导航' : '收起导航'"
          @click="collapsed = !collapsed"
        >
          <ElIcon><component :is="collapsed ? Expand : Fold" /></ElIcon>
        </button>
      </div>
    </aside>

    <section class="app-main">
      <header class="topbar">
        <h1>{{ pageTitle }}</h1>
        <button
          v-if="reminderCount"
          class="review-reminder"
          type="button"
          @click="navigate('/calendar')"
        >
          <span class="status-dot" />
          <span>{{ reminderCount }} 项日程提醒</span>
        </button>
        <button class="review-reminder" type="button" @click="navigate('/reviews')">
          <span class="status-dot" :class="{ quiet: pendingCount === 0 }" />
          <span>{{ pendingCount ? `${pendingCount} 项待审核` : '暂无待审核' }}</span>
        </button>
      </header>
      <main class="content-area">
        <RouterView />
      </main>
    </section>
  </div>
</template>

<style scoped>
.app-layout {
  display: grid;
  grid-template-columns: 176px minmax(0, 1fr);
  width: 100%;
  height: 100%;
  transition: grid-template-columns 160ms ease;
}

.app-layout.is-collapsed {
  grid-template-columns: 64px minmax(0, 1fr);
}

.app-sidebar {
  z-index: 10;
  display: flex;
  min-width: 0;
  flex-direction: column;
  background: #fff;
  border-right: 1px solid var(--jm-border-light);
}

.brand {
  display: flex;
  height: 64px;
  flex: 0 0 64px;
  gap: 10px;
  align-items: center;
  padding: 0 17px;
  border-bottom: 1px solid var(--jm-border-light);
  overflow: hidden;
}

.brand-mark {
  position: relative;
  display: flex;
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  align-items: flex-end;
  justify-content: center;
  gap: 2px;
  padding: 7px 5px;
  background: var(--jm-primary);
  border-radius: 8px;
}

.brand-mark span {
  width: 3px;
  background: #fff;
  border-radius: 2px;
}

.brand-mark span:nth-child(1) {
  height: 7px;
}

.brand-mark span:nth-child(2) {
  height: 14px;
}

.brand-mark span:nth-child(3) {
  height: 10px;
}

.brand-copy {
  display: grid;
  min-width: 0;
  white-space: nowrap;
}

.brand-copy strong {
  font-size: 15px;
  letter-spacing: 0.04em;
}

.brand-copy small {
  margin-top: 1px;
  color: var(--jm-text-tertiary);
  font-size: 9px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.app-nav {
  display: grid;
  gap: 4px;
  padding: 14px 10px;
}

.nav-item {
  position: relative;
  display: flex;
  width: 100%;
  height: 40px;
  gap: 11px;
  align-items: center;
  padding: 0 12px;
  color: var(--jm-text-secondary);
  background: transparent;
  border: 0;
  border-radius: 6px;
  cursor: pointer;
  white-space: nowrap;
}

.nav-item:hover {
  color: var(--jm-text);
  background: #f5f6f7;
}

.nav-item.active {
  color: #245bdb;
  font-weight: 600;
  background: var(--jm-primary-soft);
}

.nav-badge {
  min-width: 18px;
  height: 18px;
  margin-left: auto;
  padding: 0 5px;
  color: #fff;
  font-size: 11px;
  line-height: 18px;
  text-align: center;
  background: var(--jm-danger);
  border-radius: 9px;
}

.is-collapsed .nav-item {
  justify-content: center;
  padding: 0;
}

.is-collapsed .nav-badge {
  position: absolute;
  top: 3px;
  right: 2px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  line-height: 16px;
}

.sidebar-footer {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-top: auto;
  padding: 10px;
  border-top: 1px solid var(--jm-border-light);
}

.sidebar-footer > .nav-item {
  min-width: 0;
  flex: 1;
  padding: 0 10px;
}

.collapse-button {
  display: grid;
  width: 34px;
  height: 40px;
  flex: 0 0 34px;
  color: var(--jm-text-tertiary);
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  place-items: center;
}

.collapse-button:hover {
  color: var(--jm-text-secondary);
  background: #f5f6f7;
  border-color: var(--jm-border-light);
}

.is-collapsed .sidebar-footer {
  display: grid;
  gap: 4px;
}

.is-collapsed .sidebar-footer > .nav-item {
  width: 100%;
  padding: 0;
}

.is-collapsed .collapse-button {
  width: 32px;
  height: 30px;
  margin: 0 auto;
}

.app-main {
  display: grid;
  min-width: 0;
  min-height: 0;
  grid-template-rows: 64px minmax(0, 1fr);
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid var(--jm-border-light);
}

.topbar h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.review-reminder {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 7px 10px;
  color: var(--jm-text-secondary);
  font-size: 13px;
  background: transparent;
  border: 0;
  border-radius: 6px;
  cursor: pointer;
}

.review-reminder:hover {
  background: #f5f6f7;
}

.status-dot {
  width: 7px;
  height: 7px;
  background: var(--jm-warning);
  border-radius: 50%;
}

.status-dot.quiet {
  background: #a7abb2;
}

.content-area {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

@media (max-width: 720px) {
  .app-layout,
  .app-layout.is-collapsed {
    grid-template-columns: 56px minmax(0, 1fr);
  }

  .brand {
    padding: 0 13px;
  }

  .brand-copy,
  .nav-item > span:not(.nav-badge),
  .collapse-button {
    display: none;
  }

  .nav-item {
    justify-content: center;
    padding: 0;
  }

  .topbar {
    padding: 0 16px;
  }

  .review-reminder span:last-child {
    display: none;
  }
}
</style>
