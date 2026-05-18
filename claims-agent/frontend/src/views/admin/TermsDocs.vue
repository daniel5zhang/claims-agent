<template>
  <div class="pg"><h2>产品条款文档</h2>
    <div class="filters"><select v-model="product"><option>好医保·癌症特药险</option><option>悠臻保（特药责任）</option></select></div>
    <table><thead><tr><th>版本号</th><th>上传时间</th><th>上传人</th><th>状态</th><th>操作</th></tr></thead><tbody><tr v-for="d in docs" :key="d.id"><td>{{d.version}}</td><td>{{d.time}}</td><td>{{d.uploader}}</td><td><span :class="d.current?'tag current':'tag'">{{d.current?'当前':'历史'}}</span></td><td><button @click="download(d)">下载</button><button v-if="!d.current" @click="setCurrent(d)">设为当前</button></td></tr></tbody></table>
    <div class="upload"><h3>上传新版本</h3><input type="file" accept=".pdf"><input placeholder="版本说明" style="margin-left:8px"><button class="btn primary" @click="upload">上传</button></div>
  </div>
</template>
<script setup>
import { ref } from 'vue'
const product=ref('好医保·癌症特药险')
const docs=ref([{id:1,version:'v2024.03',time:'2024-03-15',uploader:'管理员',current:true},{id:2,version:'v2023.12',time:'2023-12-01',uploader:'管理员',current:false}])
function download(d){alert('下载: '+d.version)}
function setCurrent(d){alert('设为当前版本: '+d.version)}
function upload(){alert('条款文档上传成功')}
</script>
<style scoped>.pg{padding:24px}.filters{margin-bottom:16px}select{padding:6px 10px;border:1px solid #d9d9d9;border-radius:4px}table{width:100%;border-collapse:collapse;background:#fff;border-radius:6px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,.08)}th,td{padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:13px}th{background:#fafafa}.tag{padding:2px 8px;border-radius:10px;font-size:11px;background:#f0f0f0}.tag.current{background:#f6ffed;color:#52c41a}.upload{background:#fff;padding:16px;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.08)}.btn{padding:6px 16px;border:1px solid #d9d9d9;border-radius:4px;background:#fff;cursor:pointer}.btn.primary{background:#1a73e8;color:#fff;border:none}</style>