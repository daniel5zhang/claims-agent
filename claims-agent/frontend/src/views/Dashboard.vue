<template>
  <div class="dash">
    <h2>概览 Dashboard</h2>
    <div class="cards">
      <div class="card" v-for="c in stats" :key="c.label">
        <div class="num">{{ c.value }}</div><div class="lbl">{{ c.label }}</div>
      </div>
    </div>
    <div class="box">
      <h3>我的待办</h3>
      <table><thead><tr><th>案件号</th><th>被保险人</th><th>状态</th><th>操作</th></tr></thead>
      <tbody><tr v-for="c in todo" :key="c.id">
        <td><router-link :to="'/cases/'+c.id">{{ c.case_no }}</router-link></td>
        <td>{{ c.insured_name }}</td><td><span :class="'tag tag-'+c.status">{{ labels[c.status]||c.status }}</span></td>
        <td><router-link :to="'/cases/'+c.id">查看</router-link></td>
      </tr></tbody></table>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { useCaseStore } from '../stores/cases'
const store = useCaseStore()
const stats = ref([{label:'案件总数',value:0},{label:'待处理',value:0},{label:'审核中',value:0},{label:'已完成',value:0},{label:'待补材',value:0},{label:'转人工',value:0}])
const todo = ref([])
const labels = {pending:'待处理',running:'审核中',completed:'已完成',supplement_required:'待补材',manual_review:'转人工',cancelled:'已撤销'}
onMounted(async () => {
  await store.fetchList(); todo.value = store.list.slice(0, 5)
  try { const r = await fetch('/api/v1/stats/'); const d = await r.json()
    stats.value = [{label:'案件总数',value:d.total},{label:'待处理',value:d.pending},{label:'审核中',value:d.running},{label:'已完成',value:d.completed},{label:'待补材',value:d.supplement_required},{label:'转人工',value:d.manual_review}]
  } catch {}
})
</script>
<style scoped>
.dash { padding:24px; } h2 { margin-bottom:16px; }
.cards { display:flex; gap:16px; margin-bottom:24px; flex-wrap:wrap; }
.cards .card { flex:1; min-width:140px; background:#fff; padding:20px; border-radius:6px; box-shadow:0 1px 4px rgba(0,0,0,.08); text-align:center; }
.cards .num { font-size:28px; font-weight:700; color:#1a73e8; } .cards .lbl { font-size:13px; color:#666; margin-top:4px; }
.box { background:#fff; padding:20px; border-radius:6px; box-shadow:0 1px 4px rgba(0,0,0,.08); }
h3 { margin-bottom:12px; font-size:15px; }
table { width:100%; border-collapse:collapse; }
th,td { padding:8px 12px; text-align:left; border-bottom:1px solid #f0f0f0; font-size:13px; } th { background:#fafafa; font-weight:600; }
.tag { display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px; }
.tag-pending { background:#f0f0f0; color:#666; } .tag-running { background:#e6f7ff; color:#1890ff; } .tag-completed { background:#f6ffed; color:#52c41a; }
</style>
