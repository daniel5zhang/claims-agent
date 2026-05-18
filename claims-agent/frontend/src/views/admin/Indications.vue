<template>
  <div class="pg"><h2>适应症要点库</h2>
    <div class="filters"><select v-model="drug"><option v-for="d in drugs" :key="d" :value="d">{{d}}</option></select></div>
    <div class="card" v-for="pt in points" :key="pt.name"><h3>{{pt.name}}</h3><p class="std">{{pt.criteria}}</p><div class="compare"><span>条款约定: {{pt.terms}}</span><span v-if="pt.terms!==pt.manual" class="diff">说明书: {{pt.manual}}</span></div></div>
  </div>
</template>
<script setup>
import { ref } from 'vue'
const drug=ref('来那度胺胶囊')
const drugs=['来那度胺胶囊','塞普替尼胶囊','硼替佐米粉针']
const points=ref([
  {name:'多发性骨髓瘤，复发或难治性',criteria:'确诊为多发性骨髓瘤，且属于复发或难治性',terms:'复发或难治性多发性骨髓瘤',manual:'多发性骨髓瘤'},
  {name:'既往至少接受过一种治疗',criteria:'既往至少接受过一种治疗方案',terms:'既往至少一种治疗',manual:'至少一种治疗'},
  {name:'成人患者(≥18岁)',criteria:'年龄≥18岁的成人患者',terms:'成人',manual:'18岁以上'},
])
</script>
<style scoped>.pg{padding:24px}.filters{margin-bottom:16px}select{padding:6px 10px;border:1px solid #d9d9d9;border-radius:4px}.card{background:#fff;padding:16px;margin-bottom:12px;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.08)}h3{font-size:14px;margin-bottom:8px}.std{color:#666;font-size:13px;margin-bottom:8px}.compare{display:flex;gap:24px;font-size:12px}.diff{color:#ff4d4f}</style>