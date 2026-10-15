import { defineStore } from 'pinia'

import { emailAccountApi, emailApi } from '@/api'
import type { EmailAccount, EmailDetail, EmailListItem, EmailSyncResult } from '@/types/api'

export const useMailStore = defineStore('mail', {
  state: () => ({
    accountsById: {} as Record<number, EmailAccount>,
    emailsById: {} as Record<number, EmailListItem>,
    selectedEmailId: null as number | null,
    pageIds: [] as number[],
    total: 0,
    offset: 0,
    limit: 50,
    loading: false,
    invalidatedIds: new Set<number>(),
  }),
  getters: {
    accounts: (state) => Object.values(state.accountsById),
    emails: (state) => state.pageIds.flatMap((id) => state.emailsById[id] ?? []),
  },
  actions: {
    async loadAccounts() {
      const rows = await emailAccountApi.list()
      this.accountsById = Object.fromEntries(rows.map((item) => [item.id, item]))
      return rows
    },
    async loadPage(params: Parameters<typeof emailApi.query>[0] = {}) {
      this.loading = true
      try {
        const page = await emailApi.query({
          offset: params.offset ?? this.offset,
          limit: params.limit ?? this.limit,
          ...params,
        })
        for (const email of page.items) this.emailsById[email.id] = email
        this.pageIds = page.items.map((item) => item.id)
        this.total = page.total
        this.offset = page.offset
        this.limit = page.limit
        return page
      } finally {
        this.loading = false
      }
    },
    async refreshEmail(id: number): Promise<EmailDetail> {
      const email = await emailApi.detail(id)
      this.emailsById[id] = email
      this.invalidatedIds.delete(id)
      return email
    },
    async syncAndProcess(accountId: number): Promise<EmailSyncResult> {
      const result = await emailAccountApi.sync(accountId)
      await this.loadPage({ account_id: accountId, offset: 0 })
      return result
    },
    invalidate(id: number | null) {
      if (id) this.invalidatedIds.add(id)
    },
  },
})
