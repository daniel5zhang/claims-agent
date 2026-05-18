<template>
  <div class="pg"><h2>评测管理</h2>
    <div class="box"><h3>评测指标</h3><div class="metrics"><div v-for="m in metrics" :key="m.name" class="metric"><div class="val">{{m.value}}</div><div class="nm">{{m.name}}</div></div></div></div>
    <div class="box"><h3>评测数据集</h3><p>数据来源: 旧系统规则级标记案件 | 已拉取: 7条 | 目标: 200+ 条</p><button class="btn primary" @click="runEval">运行评测</button></div>
  </div>
</template>
<script setup>
import { ref } from 'vue'
const metrics=ref([{name:'决策一致率',value:'待评测'},{name:'拒赔精确率',value:'待评测'},{name:'补材召回率',value:'待评测'},{name:'规则级准确率',value:'待评测'},{name:'规则覆盖率',value:'待评测'},{name:'平均处理时长',value:'待评测'}])
function runEval(){alert('评测任务已加入队列')}
</script>
<style scoped>.pg{padding:24px}.box{background:#fff;padding:20px;border-radius:6px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,.08)}.metrics{display:flex;gap:16px;flex-wrap:wrap}.metric{flex:1;min-width:120px;text-align:center;padding:16px}.val{font-size:20px;font-weight:700;color:#1a73e8}.nm{font-size:12px;color:#666;margin-top:4px}.btn{padding:8px 20px;border:1px solid #d9d9d9;border-radius:4px;background:#fff;cursor:pointer}.btn.primary{background:#1a73e8;color:#fff;border:none}</style>