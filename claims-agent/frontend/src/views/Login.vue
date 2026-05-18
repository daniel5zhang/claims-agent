<template>
  <div class="login">
    <form @submit.prevent="doLogin" class="card">
      <h1>特药理赔智能审核系统</h1>
      <input v-model="username" placeholder="账号" autocomplete="username" />
      <input v-model="password" type="password" placeholder="密码" autocomplete="current-password" />
      <button type="submit" :disabled="auth.loading">{{ auth.loading ? '登录中...' : '登 录' }}</button>
      <p class="divider">— 或 —</p>
      <button type="button" class="dingtalk">钉钉扫码登录</button>
      <p v-if="error" class="error">{{ error }}</p>
    </form>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
const auth = useAuthStore(); const router = useRouter()
const username = ref('admin'); const password = ref('admin123'); const error = ref('')
async function doLogin() {
  const ok = await auth.login(username.value, password.value)
  ok ? router.push('/') : error.value = '用户名或密码错误'
}
</script>
<style scoped>
.login { display:flex; align-items:center; justify-content:center; min-height:100vh; background:#f0f2f5; }
.card { background:#fff; padding:40px; border-radius:8px; box-shadow:0 2px 12px rgba(0,0,0,.1); width:380px; text-align:center; }
h1 { font-size:22px; margin-bottom:24px; color:#1a73e8; }
input { width:100%; padding:10px; margin-bottom:12px; border:1px solid #d9d9d9; border-radius:4px; box-sizing:border-box; }
button { width:100%; padding:10px; border:none; border-radius:4px; background:#1a73e8; color:#fff; font-size:15px; cursor:pointer; }
button:disabled { opacity:.6; }
button.dingtalk { background:#fff; color:#333; border:1px solid #d9d9d9; }
.divider { color:#999; margin:16px 0; }
.error { color:#ff4d4f; margin-top:8px; }
</style>
