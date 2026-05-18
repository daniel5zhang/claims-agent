<template>
  <div class="pg"><h2>批量队列管理</h2>
    <div class="cards"><div class="card" v-for="s in stats" :key="s.label"><div class="num">{{s.value}}</div><div class="lbl">{{s.label}}</div></div></div>
    <div class="box"><h3>并发控制</h3><input type="range" v-model="concurrency" min="1" max="10"> {{concurrency}}/10</div>
    <table><thead><tr><th>任务ID</th><th>案件数</th><th>状态</th><th>开始时间</th><th>耗时</th><th>重试</th><th>操作</th></tr></thead><tbody><tr v-for="t in tasks" :key="t.id"><td>{{t.id}}</td><td>{{t.count}}</td><td><span :class="'tag tag-'+t.status">{{t.status}}</span></td><td>{{t.start}}</td><td>{{t.duration}}</td><td>{{t.retries}}</td><td><button v-if="t.status==='failed'" @click="retry(t)">重试</button></td></tr></tbody></table>
  </div>
</template>
<script setup>
import { ref } from 'vue'
const concurrency=ref(3)
const stats=ref([{label:'待执行',value:0},{label:'执行中',value:0},{label:'已完成',value:105},{label:'失败',value:0}])
const tasks=ref([{id:'batch-001',count:5,status:'completed',start:'2026-05-16 10:00',duration:'45s',retries:0},{id:'batch-002',count:10,status:'failed',start:'2026-05-16 10:30',duration:'120s',retries:3}])
function retry(t){alert('重试: '+t.id)}
</script>
<style scoped>.pg{padding:24px}.cards{display:flex;gap:16px;margin-bottom:16px}.card{flex:1;background:#fff;padding:16px;border-radius:6px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,.08)}.num{font-size:24px;font-weight:700;color:#1a73e8}.lbl{font-size:12px;color:#666}.box{background:#fff;padding:16px;border-radius:6px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,.08)}table{width:100%;border-collapse:collapse;background:#fff;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.08)}th,td{padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:13px}th{background:#fafafa}.tag{padding:2px 8px;border-radius:10px;font-size:11px}.tag-completed{background:#f6ffed;color:#52c41a}.tag-failed{background:#fff2f0;color:#ff4d4f}button{padding:4px 12px}</style>