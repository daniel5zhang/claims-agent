import { defineStore } from 'pinia'
import { api } from '../api'

export const useAuthStore = defineStore('auth', {
  state: () => ({ user: null, loading: false }),
  actions: {
    async login(username, password) {
      this.loading = true
      try {
        const r = await api.login({ username, password })
        if (r.ok) { this.user = r; return true }
        return false
      } finally { this.loading = false }
    },
    async logout() { await api.logout(); this.user = null },
    async check() { try { this.user = await api.me() } catch { this.user = null } },
  },
})
