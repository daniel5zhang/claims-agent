<template>
  <div class="pg"><h2>补材提交</h2>
    <div class="card"><h3>缺材清单</h3>
      <table><thead><tr><th>材料名称</th><th>关联责任</th><th>说明</th><th>状态</th><th>操作</th></tr></thead>
      <tbody><tr v-for="(item,i) in items" :key="i"><td>{{item.name}}</td><td>{{item.liability}}</td><td>{{item.reason}}</td><td><span :class="'tag tag-'+item.status">{{item.status==='done'?'已提交':'待提交'}}</span></td><td><input type="file" @change="upload(i,$event)"><button @click="submit(i)" :disabled="!files[i]">提交</button></td></tr></tbody></table>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'; import { api } from '../api'; import { useRoute } from 'vue-router'
const route=useRoute(); const items=ref([]); const files=ref({})
onMounted(async()=>{
  try{const c=await api.getCase(route.query.caseId||route.params.id); items.value=(c.supplement_items||[{name:'处方原件',liability:'特药责任',reason:'处方图片模糊',status:'pending'},{name:'购药发票',liability:'特药责任',reason:'发票未上传',status:'done'}])}catch{}
})
function upload(i,e){files.value[i]=e.target.files[0]}
async function submit(i){if(files.value[i]){items.value[i].status='done';files.value[i]=null}}
</script>
<style scoped>.pg{padding:24px}.card{background:#fff;padding:20px;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.08)}h3{margin-bottom:12px}table{width:100%;border-collapse:collapse}th,td{padding:8px 12px;text-align:left;border-bottom:1px solid #f0f0f0;font-size:13px}th{background:#fafafa}.tag{padding:2px 8px;border-radius:10px;font-size:11px}.tag-pending{background:#fff7e6;color:#fa8c16}.tag-done{background:#f6ffed;color:#52c41a}input[type=file]{font-size:12px}button{margin-left:8px;padding:4px 12px;border:1px solid #d9d9d9;border-radius:4px;background:#fff;cursor:pointer}</style>