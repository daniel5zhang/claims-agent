<template>
  <div class="list">
    <h2>案件列表</h2>
    <div class="filters">
      <select v-model="store.filter.status" @change="load"><option value="">全部状态</option><option v-for="(v,k) in labels" :key="k" :value="k">{{ v }}</option></select>
      <select v-model="store.filter.claim_type" @change="load"><option value="">全部险种</option><option value="SP">特药险</option><option value="MED">医疗险</option></select>
      <button class="btn" @click="load">搜索</button>
      <button class="btn primary" @click="batchAudit" :disabled="!selected.length">批量审核({{selected.length}})</button>
      <button class="btn sync" @click="showSync=!showSync">📥 同步旧系统</button>
    </div>
    <div v-if="showSync" class="sync-panel">
      <h4>从旧系统同步案件</h4>
      <div class="sync-row">
        <select v-model="syncProject"><option value="">选择项目</option><option v-for="p in projects" :key="p.id" :value="p.id">{{p.name}}</option></select>
        <button class="btn primary" @click="doSync" :disabled="syncing">{{syncing?'同步中...':'开始同步'}}</button>
      </div>
      <p v-if="syncResult" :class="syncResult.error?'err':'ok'">{{syncResult.error||'✅ 同步完成: '+syncResult.synced+' 条'}}</p>
    </div>
    <table>
      <thead><tr><th><input type="checkbox" @change="toggleAll"></th><th>案件号</th><th>被保险人</th><th>险种</th><th>报案时间</th><th>状态</th><th>来源</th><th>操作</th></tr></thead>
      <tbody><tr v-for="c in store.list" :key="c.id">
        <td><input type="checkbox" :value="c.id" v-model="selected"></td>
        <td><router-link :to="'/cases/'+c.id">{{ c.case_no }}</router-link></td>
        <td>{{ c.insured_name }}</td><td>{{ c.claim_type }}</td><td>{{ c.report_date?.slice(0,10) }}</td>
        <td><span :class="'tag tag-'+c.status">{{ labels[c.status]||c.status }}</span></td>
        <td><span class="source">{{ c.source_system }}</span></td>
        <td><router-link :to="'/cases/'+c.id">查看</router-link> <button class="lnk" @click="run(c.id)">审核</button> <button class="lnk del" @click="del(c.id)">撤销</button></td>
      </tr></tbody>
    </table>
    <div class="pager"><button :disabled="store.filter.page<=1" @click="store.filter.page--;load()">上一页</button> <span>{{store.total}} 条</span> <button @click="store.filter.page++;load()">下一页</button></div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'; import { useCaseStore } from '../stores/cases'; import { api } from '../api'
const store = useCaseStore(); const selected = ref([]); const showSync = ref(false); const syncing = ref(false); const syncResult = ref(null); const syncProject = ref('')
const projects = ref([{id:'00c16b960f5f4c3c941d0c0c77dbff86',name:'好医保·癌症特药险'},{id:'0a7a9baef94349779d6d9040852d498c',name:'人保健康-悠臻保（特药责任）'},{id:'4565c50038c044cba8a65f3379c12f2a',name:'海南乐城特药险2025版A款'},{id:'4b028c790b024e2e8c5dc1a9de5ce3c6',name:'湖南爱民保2022'}])
const labels = {pending:'待处理',running:'审核中',completed:'已完成',supplement_required:'待补材',manual_review:'转人工',error:'异常',cancelled:'已撤销'}
async function load(){ await store.fetchList(); selected.value=[] }
async function run(id){ await store.audit(id); await load() }
async function del(id){ if(confirm('撤销?')){ await store.cancel(id); await load() } }
async function batchAudit(){ await store.batchAudit(selected.value); await load() }
function toggleAll(e){ selected.value=e.target.checked?store.list.map(c=>c.id):[] }
async function doSync(){
  syncing.value=true; syncResult.value=null
  try{ const r = await api.syncCases({project_id:syncProject.value}); syncResult.value=r; await load() }
  catch(e){ syncResult.value={error:e.message} }
  syncing.value=false
}
onMounted(load)
</script>
<style scoped>
.list{padding:24px}h2{margin-bottom:16px}
.filters{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}
select{padding:6px 10px;border:1px solid #d9d9d9;border-radius:4px}
.btn{padding:6px 16px;border:1px solid #d9d9d9;border-radius:4px;background:#fff;cursor:pointer;font-size:13px}
.btn.primary{background:#1a73e8;color:#fff;border:none}.btn:disabled{opacity:.5}
.btn.sync{background:#f0f7ff;color:#1a73e8;border-color:#1a73e8}
.sync-panel{background:#fafafa;border:1px solid #e8e8e8;border-radius:6px;padding:16px;margin-bottom:16px}
.sync-panel h4{margin-bottom:8px}.sync-row{display:flex;gap:8px}
.ok{color:#52c41a;margin-top:8px}.err{color:#ff4d4f;margin-top:8px}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:6px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08)}
th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #f0f0f0;font-size:13px}th{background:#fafafa;font-weight:600}
.tag{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px}
.tag-pending{background:#f0f0f0;color:#666}.tag-running{background:#e6f7ff;color:#1890ff}.tag-completed{background:#f6ffed;color:#52c41a}.tag-error{background:#fff2f0;color:#ff4d4f}
.source{font-size:11px;color:#999}
.lnk{background:none;border:none;color:#1a73e8;cursor:pointer;margin-left:8px;font-size:12px}.lnk.del{color:#ff4d4f}
.pager{display:flex;gap:12px;align-items:center;justify-content:center;margin-top:16px;font-size:13px}
</style>
