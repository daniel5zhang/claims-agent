import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../views/ChatView.vue'
import SchemeView from '../views/SchemeView.vue'

const routes = [
  {
    path: '/',
    redirect: '/chat'
  },
  {
    path: '/chat',
    name: 'Chat',
    component: ChatView,
    meta: { title: '产品顾问' }
  },
  {
    path: '/scheme/:schemeId?',
    name: 'Scheme',
    component: SchemeView,
    meta: { title: '方案详情' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
