import { defineStore } from 'pinia'
import { api, connectWS } from '../api'

export const useCaseStore = defineStore('cases', {
  state: () => ({
    list: [], total: 0, current: null, events: [], ws: null,
    filter: { status: '', claim_type: '', page: 1, page_size: 20 },
  }),
  actions: {
    async fetchList() {
      const r = await api.listCases(this.filter)
      this.list = r.results || []; this.total = r.count || 0
    },
    async fetchCase(id) {
      this.current = await api.getCase(id)
    },
    async audit(id) { await api.auditCase(id); await this.fetchCase(id) },
    async cancel(id) { await api.cancelCase(id); await this.fetchList() },
    async batchAudit(ids) { await api.batchAudit(ids); await this.fetchList() },
    watchCase(id) {
      this.events = []
      if (this.ws) this.ws.close()
      this.ws = connectWS(id, (e) => this.events.push(e))
    },
    unwatch() { if (this.ws) { this.ws.close(); this.ws = null } },
  },
})
