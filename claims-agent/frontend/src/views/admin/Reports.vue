<template>
  <div class="pg"><h2>报表中心</h2>
    <div class="box"><h3>生成报表</h3><select v-model="reportType"><option>月度汇总</option><option>项目汇总</option><option>审核员工作量</option><option>规则执行统计</option></select><input type="month"><button class="btn primary" @click="generate">生成</button></div>
    <table><thead><tr><th>报表名称</th><th>类型</th><th>生成时间</th><th>状态</th><th>操作</th></tr></thead><tbody><tr v-for="r in reports" :key="r.id"><td>{{r.name}}</td><td>{{r.type}}</td><td>{{r.time}}</td><td>{{r.status}}</td><td><button @click="download(r)">下载</button></td></tr></tbody></table>
  </div>
</template>
<script setup>
import { ref } from 'vue'
const reportType=ref('月度汇总')
const reports=ref([{id:1,name:'2026年5月月度汇总',type:'月度汇总',time:'2026-05-16',status:'已完成'}])
function generate(){alert('报表生成任务已加入队列')}
function download(r){alert('下载: '+r.name)}
</script>
<style scoped>.pg{padding:24px}.box{background:#fff;padding:16px;border-radius:6px;margin-bottom:16px;display:flex;align-items:center;gap:12px;box-shadow:0 1px 4px rgba(0,0,0,.08)}select,input{padding:6px 10px;border:1px solid #d9d9d9;border-radius:4px}table{width:100%;border-collapse:collapse;background:#fff;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.08)}th,td{padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:13px}th{background:#fafafa}.btn{padding:6px 16px;border:1px solid #d9d9d9;border-radius:4px;background:#fff;cursor:pointer}.btn.primary{background:#1a73e8;color:#fff;border:none}</style>