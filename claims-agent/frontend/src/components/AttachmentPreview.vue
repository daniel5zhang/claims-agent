<template>
  <div class="att-preview">
    <div class="thumbnails">
      <div v-for="a in attachments" :key="a.id" :class="{active:active===a.id}" @click="active=a.id" class="thumb">
        <span v-if="a.mime_type?.startsWith('image')">🖼️</span>
        <span v-else-if="a.mime_type==='application/pdf'">📄</span>
        <span v-else>📎</span>
        <small>{{a.file_name}}</small>
      </div>
    </div>
    <div class="viewer" v-if="active">
      <div class="toolbar">
        <button @click="mode='preview'" :class="{active:mode==='preview'}">预览</button>
        <button @click="mode='ocr'" :class="{active:mode==='ocr'}">识别内容</button>
      </div>
      <div v-if="mode==='preview'" class="preview-area">
        <img v-if="activeFile?.mime_type?.startsWith('image')" :src="'/api/v1/files/'+active" style="max-width:100%">
        <div v-else class="pdf-placeholder">PDF 预览 (需浏览器插件)</div>
      </div>
      <div v-if="mode==='ocr'" class="ocr-content">
        <pre>{{ ocrText || '尚未OCR识别' }}</pre>
      </div>
    </div>
  </div>
</template>
<script setup>
import { ref, computed } from 'vue'
const props = defineProps({ attachments: { type: Array, default: () => [] } })
const active = ref(null); const mode = ref('preview')
const activeFile = computed(() => props.attachments.find(a => a.id === active.value))
const ocrText = ref('')
watch(active, async (id) => {
  if (id) { try { const r = await fetch('/api/v1/files/'+id+'/ocr/'); ocrText.value = (await r.json()).text || '' } catch {} }
})
import { watch } from 'vue'
</script>
<style scoped>
.att-preview{display:flex;gap:16px}.thumbnails{width:200px;max-height:400px;overflow-y:auto}.thumb{padding:8px;cursor:pointer;border-radius:4px;display:flex;align-items:center;gap:8px;font-size:12px}.thumb:hover,.thumb.active{background:#f0f7ff}.viewer{flex:1}.toolbar{display:flex;gap:4px;margin-bottom:12px}.toolbar button{padding:4px 12px;border:1px solid #d9d9d9;border-radius:4px;background:#fff;cursor:pointer;font-size:12px}.toolbar button.active{background:#1a73e8;color:#fff}.preview-area{min-height:200px;background:#fafafa;border-radius:4px;display:flex;align-items:center;justify-content:center}.pdf-placeholder{color:#999}.ocr-content pre{background:#f8f8f8;padding:12px;border-radius:4px;font-size:12px;white-space:pre-wrap}
</style>