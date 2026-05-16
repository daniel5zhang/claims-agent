import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import * as Sentry from '@sentry/vue'
import App from './App.vue'

const routes = [
  { path: '/', name: 'dashboard', component: () => import('./views/Dashboard.vue') },
  { path: '/cases', name: 'cases', component: () => import('./views/CaseList.vue') },
  { path: '/cases/:id', name: 'case-detail', component: () => import('./views/CaseDetail.vue') },
  // 管理端路由（按需加载）
  { path: '/admin/rules', name: 'rules', component: () => import('./views/admin/RuleList.vue') },
  { path: '/admin/config', name: 'config', component: () => import('./views/admin/SystemConfig.vue') },
  // C 端路由
  { path: '/c/', name: 'c-home', component: () => import('./views/c/HomePage.vue') },
  { path: '/c/cases/:id', name: 'c-case', component: () => import('./views/c/CaseView.vue') },
]

const router = createRouter({ history: createWebHistory(), routes })
const pinia = createPinia()
const app = createApp(App)

if (import.meta.env.PROD) {
  Sentry.init({ app, dsn: import.meta.env.VITE_SENTRY_DSN, integrations: [Sentry.browserTracingIntegration({ router })], tracesSampleRate: 0.1 })
}

app.use(router).use(pinia).mount('#app')
