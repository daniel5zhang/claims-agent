<template>
  <div class="pg"><h2>系统审计日志</h2>
    <div class="filters"><select v-model="logType"><option value="">全部类型</option><option>操作日志</option><option>Agent执行日志</option><option>模型调用日志</option></select><input type="date"><button>搜索</button></div>
    <table><thead><tr><th>时间</th><th>操作人</th><th>类型</th><th>对象</th><th>详情</th></tr></thead><tbody><tr v-for="l in logs" :key="l.id"><td>{{l.time}}</td><td>{{l.user}}</td><td>{{l.type}}</td><td>{{l.target}}</td><td>{{l.detail}}</td></tr></tbody></table>
  </div>
</template>
<script setup>
import { ref } from 'vue'
const logType=ref('')
const logs=ref([{id:1,time:'2026-05-16 15:25',user:'admin',type:'操作日志',target:'Case#001',detail:'执行智能审核'},{id:2,time:'2026-05-16 14:10',user:'系统',type:'Agent执行',target:'Phase 5',detail:'规则审核完成 pass=14 reject=1'}])
</script>
<style scoped>.pg{padding:24px}.filters{display:flex;gap:8px;margin-bottom:16px}select,input{padding:6px 10px;border:1px solid #d9d9d9;border-radius:4px}button{padding:6px 16px;border:1px solid #d9d9d9;border-radius:4px;background:#fff;cursor:pointer}table{width:100%;border-collapse:collapse;background:#fff;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.08)}th,td{padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:13px}th{background:#fafafa}</style>