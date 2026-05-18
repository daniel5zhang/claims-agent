<template>
  <div class="c" v-if="c"><h2>{{c.case_no}}</h2>
    <div class="info"><p><strong>出险人:</strong> {{c.insured_name}}</p><p><strong>诊断:</strong> {{c.diagnosis}}</p><p><strong>状态:</strong> {{labels[c.status]||c.status}}</p><p><strong>报案时间:</strong> {{c.report_date?.slice(0,10)}}</p></div>
    <div class="supplement"><h3>补材上传</h3><div v-if="items.length"><div v-for="(item,i) in items" :key="i" class="item"><span>{{item.name}}</span><span class="reason">{{item.reason}}</span><input type="file" @change="onFile(i,$event)"><button @click="submit(i)" :disabled="!files[i]">提交</button></div></div><p v-else>暂无缺材清单</p></div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'; import { useRoute } from 'vue-router'
const route=useRoute(); const c=ref(null); const files=ref({}); const items=ref([])
const labels={pending:'待处理',running:'审核中',completed:'已完成',supplement_required:'待补材'}
onMounted(async()=>{try{const r=await fetch('/api/v1/c/cases/'+route.params.id);c.value=await r.json()}catch{}})
function onFile(i,e){files.value[i]=e.target.files[0]}
async function submit(i){if(files.value[i]){try{await fetch('/api/v1/c/cases/'+route.params.id+'/supplement/',{method:'POST'});items.value[i].status='done';files.value[i]=null}catch{}}
}
</script>
<style scoped>.c{padding:24px;max-width:600px}h2{margin-bottom:16px}.info p{margin:8px 0;font-size:14px}.supplement{margin-top:24px;background:#fff;padding:20px;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.08)}.item{display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid #f0f0f0}.reason{color:#999;font-size:12px;flex:1}input[type=file]{font-size:12px}button{padding:4px 12px;border:1px solid #d9d9d9;border-radius:4px;background:#fff;cursor:pointer}button:disabled{opacity:.5}@media(max-width:768px){.c{padding:12px}.item{flex-direction:column;align-items:flex-start}}</style>