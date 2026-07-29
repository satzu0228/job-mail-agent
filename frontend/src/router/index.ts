import { createRouter, createWebHistory } from 'vue-router'

import AppLayout from '@/layouts/AppLayout.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: AppLayout,
      children: [
        { path: '', redirect: '/mail' },
        {
          path: 'mail/:emailId?',
          name: 'mail',
          component: () => import('@/views/MailView.vue'),
          meta: { title: '邮件' },
        },
        {
          path: 'applications',
          name: 'applications',
          component: () => import('@/views/ApplicationsView.vue'),
          meta: { title: '求职进度' },
        },
        {
          path: 'calendar',
          name: 'calendar',
          component: () => import('@/views/CalendarView.vue'),
          meta: { title: '日程' },
        },
        {
          path: 'reviews/:taskId?',
          name: 'reviews',
          component: () => import('@/views/ReviewsView.vue'),
          meta: { title: '审核' },
        },
        {
          path: 'settings/mailboxes',
          name: 'mailbox-settings',
          component: () => import('@/views/MailboxSettingsView.vue'),
          meta: { title: '邮箱设置' },
        },
      ],
    },
  ],
})

router.afterEach((to) => {
  document.title = `${String(to.meta.title ?? '求职邮迹')} · 求职邮迹`
})

export default router
