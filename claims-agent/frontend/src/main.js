import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'

const routes = [
  { path: '/login', name: 'login', component: () => import('./views/Login.vue'), meta: { guest: true } },
  { path: '/', name: 'dashboard', component: () => import('./views/Dashboard.vue') },
  { path: '/cases', name: 'cases', component: () => import('./views/CaseList.vue') },
  { path: '/cases/new', name: 'case-create', component: () => import('./views/CaseCreate.vue') },
  { path: '/cases/:id', name: 'case-detail', component: () => import('./views/CaseDetail.vue') },
  { path: '/cases/:id/supplement', name: 'supplement', component: () => import('./views/Supplement.vue') },
  { path: '/admin/rules', name: 'rules', component: () => import('./views/admin/RuleList.vue') },
  { path: '/admin/indications', name: 'indications', component: () => import('./views/admin/Indications.vue') },
  { path: '/admin/projects', name: 'projects', component: () => import('./views/admin/Projects.vue') },
  { path: '/admin/orgs', name: 'orgs', component: () => import('./views/admin/Organizations.vue') },
  { path: '/admin/queue', name: 'queue', component: () => import('./views/admin/Queue.vue') },
  { path: '/admin/logs', name: 'logs', component: () => import('./views/admin/AuditLogs.vue') },
  { path: '/admin/eval', name: 'eval', component: () => import('./views/admin/Evaluation.vue') },
  { path: '/admin/config', name: 'config', component: () => import('./views/admin/SystemConfig.vue') },
  { path: '/admin/reports', name: 'reports', component: () => import('./views/admin/Reports.vue') },
  { path: '/admin/drug-db', name: 'drug-db', component: () => import('./views/admin/DrugDB.vue') },
  { path: '/admin/terms', name: 'terms', component: () => import('./views/admin/TermsDocs.vue') },
  { path: '/c/', name: 'c-home', component: () => import('./views/c/HomePage.vue'), meta: { public: true } },
  { path: '/c/cases/:id', name: 'c-case', component: () => import('./views/c/CaseView.vue'), meta: { public: true } },
]

const router = createRouter({ history: createWebHistory(), routes })
router.beforeEach(async (to) => {
  if (to.meta.public || to.meta.guest) return
  try { const r = await fetch('/api/v1/auth/me/'); if (!r.ok) return '/login' } catch { return '/login' }
})

const app = createApp(App)
app.use(router).use(createPinia()).mount('#app')
