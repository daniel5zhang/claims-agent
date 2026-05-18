<template>
  <div class="evidence">
    <h4>证据溯源</h4>
    <div v-for="e in evidences" :key="e.id" class="item">
      <span :class="'dot '+e.type"></span>
      <span class="label">{{e.label}}</span>
      <span class="att">附件: {{e.attachment_id?.slice(0,8)}}...</span>
      <span v-if="e.bbox" class="bbox">坐标: [{{e.bbox.join(',')}}]</span>
    </div>
    <p v-if="!evidences.length" class="empty">暂无证据标注</p>
  </div>
</template>
<script setup>
defineProps({ evidences: { type: Array, default: () => [] } })
</script>
<style scoped>
.evidence{padding:12px}.item{display:flex;align-items:center;gap:8px;padding:6px 0;font-size:12px;border-bottom:1px solid #f0f0f0}.dot{width:8px;height:8px;border-radius:50%;display:inline-block}.dot.reject_basis{background:#ff4d4f}.dot.confirm_basis{background:#52c41a}.dot.pending{background:#faad14}.dot.supplement{background:#1890ff}.label{font-weight:500}.att,.bbox{color:#999;font-size:11px}.empty{color:#999;font-size:12px}
</style>