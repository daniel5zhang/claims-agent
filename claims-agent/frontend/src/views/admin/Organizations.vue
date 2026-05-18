<template>
  <div class="pg"><h2>组织架构 / 权限</h2>
    <div class="row"><div class="box"><h3>组织树</h3><ul class="tree"><li v-for="org in orgs" :key="org.id">{{org.name}}<ul><li v-for="d in org.depts" :key="d">{{d}}</li></ul></li></ul></div>
    <div class="box"><h3>角色权限矩阵</h3><table><thead><tr><th>角色</th><th>案件列表</th><th>案件详情</th><th>执行审核</th><th>人工介入</th><th>规则管理</th></tr></thead><tbody><tr v-for="r in roles" :key="r.name"><td>{{r.name}}</td><td v-for="p in r.perms" :key="p">{{p}}</td></tr></tbody></table></div></div>
  </div>
</template>
<script setup>
import { ref } from 'vue'
const orgs=ref([{id:1,name:'总公司',depts:['技术部','运营部','审核部']}])
const roles=ref([{name:'审核员',perms:['读','读+写','执行','介入','-']},{name:'审核主管',perms:['读','读+写','执行','介入','读']},{name:'规则管理员',perms:['读','读','-','-','读+写']},{name:'系统管理员',perms:['全部','全部','全部','全部','全部']}])
</script>
<style scoped>.pg{padding:24px}.row{display:flex;gap:16px}.box{flex:1;background:#fff;padding:20px;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.08)}h3{margin-bottom:12px}.tree{list-style:none;padding:0}.tree li{padding:4px 0}.tree ul{padding-left:16px}table{width:100%;border-collapse:collapse}th,td{padding:8px;text-align:center;border-bottom:1px solid #f0f0f0;font-size:12px}th{background:#fafafa}</style>