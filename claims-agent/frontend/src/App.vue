<template>
  <div v-if="$route.meta.public || $route.meta.guest" class="bare">
    <router-view />
  </div>
  <div v-else class="app">
    <nav>
      <span class="logo">特药理赔智能审核</span>
      <div class="links">
        <router-link to="/">Dashboard</router-link>
        <router-link to="/cases">案件列表</router-link>
        <router-link to="/cases/new">报案录入</router-link>
        <div class="dropdown">
          <span class="drop-trigger">管理端 ▾</span>
          <div class="drop-menu">
            <router-link to="/admin/rules">规则库</router-link>
            <router-link to="/admin/indications">适应症要点</router-link>
            <router-link to="/admin/projects">项目配置</router-link>
            <router-link to="/admin/orgs">组织权限</router-link>
            <router-link to="/admin/queue">批量队列</router-link>
            <router-link to="/admin/logs">审计日志</router-link>
            <router-link to="/admin/eval">评测管理</router-link>
            <router-link to="/admin/config">系统配置</router-link>
            <router-link to="/admin/reports">报表中心</router-link>
            <router-link to="/admin/drug-db">数据库管理</router-link>
            <router-link to="/admin/terms">条款文档</router-link>
          </div>
        </div>
      </div>
      <div class="right">
        <span v-if="user">{{ user.display_name || user.username }}</span>
        <button @click="doLogout">退出</button>
      </div>
    </nav>
    <main><router-view /></main>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
const router = useRouter(); const user = ref(null)
onMounted(async () => {
  try { const r = await fetch('/api/v1/auth/me/'); user.value = await r.json() } catch {}
})
async function doLogout() { await fetch('/api/v1/auth/logout/', { method: 'POST' }); router.push('/login') }
</script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f0f2f5;color:#333}
a{color:#1a73e8;text-decoration:none}
nav{display:flex;align-items:center;gap:20px;padding:0 24px;height:48px;background:#fff;border-bottom:1px solid #e8e8e8}
nav .logo{font-weight:700;font-size:15px;color:#1a73e8}
nav .links{display:flex;gap:16px;font-size:13px}
nav .right{margin-left:auto;display:flex;align-items:center;gap:12px;font-size:13px}
nav .right button{background:none;border:none;color:#1a73e8;cursor:pointer;font-size:12px}
main{min-height:calc(100vh - 48px)}@media(max-width:768px){nav{padding:0 12px;gap:8px;flex-wrap:wrap;height:auto;min-height:48px}nav .links{gap:8px;font-size:11px;flex-wrap:wrap}nav .logo{font-size:13px}.drop-menu{left:auto;right:0}}
.bare{min-height:100vh}
.dropdown{position:relative;cursor:pointer}.drop-trigger{font-size:13px}.drop-menu{display:none;position:absolute;top:100%;left:0;background:#fff;border:1px solid #e8e8e8;border-radius:4px;box-shadow:0 4px 12px rgba(0,0,0,.1);z-index:100;min-width:140px;padding:4px 0}.dropdown:hover .drop-menu{display:block}.drop-menu a{display:block;padding:6px 16px;font-size:12px;color:#333}.drop-menu a:hover{background:#f0f7ff}
</style>
