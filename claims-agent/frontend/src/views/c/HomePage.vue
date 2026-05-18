<template>
  <div class="c"><h2>我的理赔</h2>
    <table v-if="list.length"><thead><tr><th>案件号</th><th>险种</th><th>报案时间</th><th>状态</th><th>操作</th></tr></thead><tbody><tr v-for="c in list" :key="c.id"><td>{{c.case_no}}</td><td>{{c.claim_type}}</td><td>{{c.report_date?.slice(0,10)}}</td><td><span :class="'tag tag-'+c.status">{{labels[c.status]||c.status}}</span></td><td><router-link :to="'/c/cases/'+c.id">查看</router-link></td></tr></tbody></table>
    <p v-else class="empty">暂无案件</p>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
const list=ref([]); const labels={pending:'待处理',running:'审核中',completed:'已完成',supplement_required:'待补材'}
onMounted(async()=>{try{const r=await fetch('/api/v1/c/cases/');list.value=await r.json()}catch{}})
</script>
<style scoped>.c{padding:24px;max-width:800px}h2{margin-bottom:16px}table{width:100%;border-collapse:collapse;background:#fff;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.08)}th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #f0f0f0;font-size:13px}th{background:#fafafa}.tag{padding:2px 8px;border-radius:10px;font-size:11px}.tag-pending{background:#f0f0f0;color:#666}.tag-running{background:#e6f7ff;color:#1890ff}.tag-completed{background:#f6ffed;color:#52c41a}.empty{color:#999;text-align:center;padding:40px}@media(max-width:768px){.c{padding:12px}th,td{font-size:11px;padding:6px 8px}}</style>