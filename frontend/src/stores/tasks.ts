import { defineStore } from 'pinia'

import { reminderApi, taskApi } from '@/api'
import type { Reminder, Task } from '@/types/api'

export const useTaskStore = defineStore('tasks', {
  state: () => ({
    tasksById: {} as Record<number, Task>,
    remindersById: {} as Record<number, Reminder>,
    pageIds: [] as number[],
    loading: false,
    invalidatedApplicationIds: new Set<number>(),
  }),
  getters: {
    tasks: (state) => state.pageIds.flatMap((id) => state.tasksById[id] ?? []),
    reminders: (state) => Object.values(state.remindersById),
  },
  actions: {
    upsert(task: Task) {
      this.tasksById[task.id] = task
      if (!this.pageIds.includes(task.id)) this.pageIds.unshift(task.id)
      if (task.application_id) this.invalidatedApplicationIds.delete(task.application_id)
    },
    async refreshRange(params: Parameters<typeof taskApi.query>[0] = {}) {
      this.loading = true
      try {
        const [page, reminders] = await Promise.all([
          taskApi.query({ offset: 0, limit: 100, ...params }),
          reminderApi.list(true),
        ])
        for (const task of page.items) this.tasksById[task.id] = task
        this.pageIds = page.items.map((task) => task.id)
        this.remindersById = Object.fromEntries(reminders.map((item) => [item.id, item]))
        return page
      } finally {
        this.loading = false
      }
    },
    async updateTask(id: number, payload: Partial<Task> & { version: number }) {
      const task = await taskApi.update(id, payload)
      this.upsert(task)
      return task
    },
    invalidateApplication(id: number | null) {
      if (id) this.invalidatedApplicationIds.add(id)
    },
  },
})
