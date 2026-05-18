<template>
  <div class="form"><h2>报案录入</h2>
    <div class="grid">
      <label>出险人姓名<input v-model="f.insured_name" placeholder="必填"></label>
      <label>身份证号<input v-model="f.id_number" placeholder="必填"></label>
      <label>联系电话<input v-model="f.phone"></label>
      <label>诊断<input v-model="f.diagnosis"></label>
      <label>就诊医院<input v-model="f.hospital_name"></label>
      <label>理赔模式<select v-model="f.claim_mode"><option value="reimbursement">事后报销</option><option value="direct">直赔</option></select></label>
      <label>险种<select v-model="f.claim_type"><option value="SP">特药险</option></select></label>
      <label>报案人姓名<input v-model="f.report_person_name"></label>
      <label>报案人电话<input v-model="f.report_person_phone"></label>
    </div>
    <div class="upload"><h3>附件上传</h3><input type="file" multiple @change="onFiles"><div v-for="(f,i) in files" :key="i" class="file">{{f.name}} ({{(f.size/1024).toFixed(0)}}KB)</div></div>
    <button class="btn primary" @click="submit" :disabled="submitting">{{submitting?'提交中...':'提交'}}</button>
    <p v-if="result" :class="result.ok?'ok':'err'">{{result.ok?'✅ 创建成功: '+result.case_no:'❌ '+result.error}}</p>
  </div>
</template>
<script setup>
import { ref, reactive } from 'vue'; import { api } from '../api'
const f = reactive({insured_name:'',id_number:'',phone:'',diagnosis:'',hospital_name:'',claim_mode:'reimbursement',claim_type:'SP',report_person_name:'',report_person_phone:''}); const files=ref([]); const submitting=ref(false); const result=ref(null)
function onFiles(e){files.value=Array.from(e.target.files)}
async function submit(){
  submitting.value=true; result.value=null
  try{
    const r = await api.createCase({...f})
    result.value={ok:true,case_no:r.case_no||'OK'}
  }catch(e){
    result.value={ok:false,error:e.message}
  }
  submitting.value=false
}
</script>
<style scoped>
.form{padding:24px;max-width:700px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px}
label{display:flex;flex-direction:column;font-size:13px;color:#666;gap:4px}
input,select{padding:8px;border:1px solid #d9d9d9;border-radius:4px}.upload{margin-bottom:16px}.file{font-size:12px;color:#666;padding:4px 0}
.btn{padding:8px 20px;border:1px solid #d9d9d9;border-radius:4px;background:#fff;cursor:pointer}.btn.primary{background:#1a73e8;color:#fff;border:none}.ok{color:#52c41a;margin-top:8px}.err{color:#ff4d4f;margin-top:8px}
</style>