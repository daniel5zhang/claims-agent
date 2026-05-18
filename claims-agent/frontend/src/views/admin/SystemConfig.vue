<template>
  <div class="pg"><h2>系统配置</h2>
    <div class="box" v-for="s in sections" :key="s.title"><h3>{{s.title}}</h3><div class="row" v-for="(v,k) in s.fields" :key="k"><label>{{k}}</label><input v-model="s.fields[k]" :type="k.includes('KEY')||k.includes('SECRET')?'password':'text'"></div></div>
    <button class="btn primary" @click="save">保存配置</button><span v-if="saved" class="ok">✅ 配置已保存</span><span v-if="error" class="err">{{error}}</span>
  </div>
</template>
<script setup>
import { reactive, ref, onMounted } from 'vue'
const saved=ref(false); const error=ref('')
const sections=reactive([
  {title:'模型配置',fields:{PRIMARY_MODEL:'qwen3.6-plus',FALLBACK_MODEL:'deepseek-v4-pro',FLASH_MODEL:'qwen3.6-flash',EMBEDDING_MODEL:'text-embedding-v3'}},
  {title:'存储配置',fields:{ATTACHMENT_STORAGE:'local',LOCAL_ATTACHMENT_PATH:'./data/attachments'}},
  {title:'SLA配置',fields:{TOTAL_HOURS:'48',WARN_BEFORE_HOURS:'4',ESCALATE_AFTER_HOURS:'8'}},
  {title:'队列配置',fields:{MAX_CONCURRENCY:'3',RETRY_LIMIT:'3'}},
])
onMounted(()=>{
  const stored = localStorage.getItem('systemConfig')
  if(stored){
    try{ const parsed=JSON.parse(stored); sections.forEach(s=>{ Object.assign(s.fields, parsed[s.title]||{}) }) }catch{}
  }
})
async function save(){
  try{
    const config = {}; sections.forEach(s=>{ config[s.title]=s.fields })
    localStorage.setItem('systemConfig', JSON.stringify(config))
    saved.value=true; error.value=''; setTimeout(()=>saved.value=false,2000)
  }catch(e){ error.value=e.message }
}
</script>
<style scoped>
.pg{padding:24px;max-width:600px}.box{background:#fff;padding:20px;border-radius:6px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,.08)}h3{margin-bottom:12px}.row{display:flex;align-items:center;gap:12px;padding:8px 0}label{width:200px;font-size:13px;color:#666}input{flex:1;padding:6px 8px;border:1px solid #d9d9d9;border-radius:4px}.btn{padding:8px 20px;border:1px solid #d9d9d9;border-radius:4px;background:#fff;cursor:pointer}.btn.primary{background:#1a73e8;color:#fff;border:none}.ok{color:#52c41a;margin-left:8px}.err{color:#ff4d4f;margin-left:8px}
</style>