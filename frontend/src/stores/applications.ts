import { defineStore } from 'pinia'

import { applicationApi, taskApi } from '@/api'
import type {
  ApplicationEvent,
  InterviewRound,
  JobApplication,
  Page,
  Task,
} from '@/types/api'

interface ApplicationDetails {
  events: ApplicationEvent[]
  rounds: InterviewRound[]
  tasks: Task[]
}

export const useApplicationStore = defineStore('applications', {
  state: () => ({
    applicationsById: {} as Record<number, JobApplication>,
    selectedApplicationId: null as number | null,
    pageIds: [] as number[],
    total: 0,
    offset: 0,
    limit: 50,
    detailsById: {} as Record<number, ApplicationDetails>,
    invalidatedIds: new Set<number>(),
    loading: false,
  }),
  getters: {
    applications: (state) =>
      state.pageIds.flatMap((id) => state.applicationsById[id] ?? []),
    selected: (state) =>
      state.selectedApplicationId
        ? state.applicationsById[state.selectedApplicationId] ?? null
        : null,
  },
  actions: {
    upsert(application: JobApplication) {
      this.applicationsById[application.id] = application
      this.invalidatedIds.delete(application.id)
      if (!this.pageIds.includes(application.id)) this.pageIds.unshift(application.id)
    },
    async loadPage(
      params: Parameters<typeof applicationApi.query>[0] = {},
    ): Promise<Page<JobApplication>> {
      this.loading = true
      try {
        const page = await applicationApi.query({
          offset: params.offset ?? this.offset,
          limit: params.limit ?? this.limit,
          ...params,
        })
        for (const application of page.items) this.upsert(application)
        this.pageIds = page.items.map((item) => item.id)
        this.total = page.total
        this.offset = page.offset
        this.limit = page.limit
        return page
      } finally {
        this.loading = false
      }
    },
    async refresh(id: number) {
      const application = await applicationApi.detail(id)
      this.upsert(application)
      return application
    },
    async loadDetails(id: number): Promise<ApplicationDetails> {
      const [eventPage, rounds, taskPage] = await Promise.all([
        applicationApi.events(id),
        applicationApi.listInterviewRounds(id),
        taskApi.query({ application_id: id, offset: 0, limit: 100 }),
      ])
      const details = { events: eventPage.items, rounds, tasks: taskPage.items }
      this.detailsById[id] = details
      return details
    },
    invalidate(id: number | null) {
      if (id) this.invalidatedIds.add(id)
    },
  },
})
