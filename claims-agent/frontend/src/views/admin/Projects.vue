<template>
  <div class="pg"><h2>项目/产品配置</h2>
    <table><thead><tr><th>项目编号</th><th>项目名称</th><th>保险公司</th><th>险种</th><th>状态机</th><th>审核组</th><th>操作</th></tr></thead>
    <tbody><tr v-for="p in projects" :key="p.id"><td>{{p.code}}</td><td>{{p.name}}</td><td>{{p.company}}</td><td>{{p.type}}</td><td>{{p.stateMachine}}</td><td>{{p.group}}</td><td><button @click="edit(p)">配置</button></td></tr></tbody></table>
  </div>
</template>
<script setup>
import { ref } from 'vue'
const projects=ref([{id:1,code:'YGCCBX-TYX',name:'好医保·癌症特药险',company:'人保健康',type:'特药险',stateMachine:'赔付>5万→转人工',group:'审核组A'},{id:2,code:'RBJK-YZB',name:'悠臻保（特药责任）',company:'人保健康',type:'特药险',stateMachine:'默认',group:'审核组B'}])
function edit(p){alert('配置: '+p.name)}
</script>
<style scoped>.pg{padding:24px}table{width:100%;border-collapse:collapse;background:#fff;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.08)}th,td{padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:13px}th{background:#fafafa}button{padding:4px 12px;border:1px solid #d9d9d9;border-radius:4px;background:#fff;cursor:pointer}</style>