<template>
  <div :class="['chat-bubble', message.role]">
    <div class="avatar">
      <el-avatar
        :size="36"
        :icon="message.role === 'user' ? UserFilled : Service"
        :class="message.role"
      />
    </div>
    <div class="content-wrapper">
      <div class="sender">{{ senderName }}</div>
      <div class="content" v-html="renderedContent"></div>
      <div v-if="timestamp" class="time">{{ formatTime(timestamp) }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { UserFilled, Service } from '@element-plus/icons-vue'
import { marked } from 'marked'

const props = defineProps({
  message: {
    type: Object,
    required: true
  }
})

const senderName = computed(() => {
  return props.message.role === 'user' ? '您' : '产品顾问'
})

const timestamp = computed(() => {
  return props.message.timestamp
})

const renderedContent = computed(() => {
  const text = props.message.content || ''
  // 移除 JSON 代码块及前后的标题文字
  let cleanText = text
    // 移除 "JSON 代码块"、"结构化数据" 等标题及后面的代码块
    .replace(/(JSON\s*代码块|结构化数据|系统数据)[\s\S]*?```json[\s\S]*?```/gi, '')
    // 移除独立的 json 代码块
    .replace(/```json[\s\S]*?```/g, '')
    // 移除其他代码块
    .replace(/```[\s\S]*?```/g, '')
    // 移除多余的空行（3行以上合并为2行）
    .replace(/\n{3,}/g, '\n\n')
    .trim()

  if (!cleanText) {
    cleanText = text
  }

  // Markdown 渲染
  return marked.parse(cleanText)
})

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped lang="scss">
.chat-bubble {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  animation: fadeIn 0.3s ease;

  &.user {
    flex-direction: row-reverse;

    .content-wrapper {
      align-items: flex-end;
    }

    .content {
      background: #409eff;
      color: #fff;
      border-radius: 12px 12px 2px 12px;
    }
  }

  &.assistant {
    .content {
      background: #fff;
      color: #303133;
      border-radius: 12px 12px 12px 2px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
  }
}

.avatar {
  flex-shrink: 0;
}

.content-wrapper {
  display: flex;
  flex-direction: column;
  max-width: 75%;
}

.sender {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.content {
  padding: 10px 14px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;

  :deep(p) {
    margin: 0 0 8px;
    &:last-child { margin-bottom: 0; }
  }

  :deep(ul), :deep(ol) {
    margin: 0 0 8px 16px;
    padding: 0;
  }

  :deep(li) {
    margin-bottom: 4px;
  }

  :deep(strong) {
    font-weight: 600;
  }

  /* Markdown 表格样式 */
  :deep(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 8px 0 12px;
    font-size: 12px;
    line-height: 1.4;
    display: block;
    overflow-x: auto;
    white-space: nowrap;
  }

  :deep(thead) {
    background: #f5f7fa;
  }

  :deep(th) {
    padding: 6px 8px;
    text-align: left;
    font-weight: 600;
    color: #303133;
    border: 1px solid #dcdfe6;
    background: #f5f7fa;
    white-space: nowrap;
  }

  :deep(td) {
    padding: 6px 8px;
    border: 1px solid #e4e7ed;
    color: #606266;
    white-space: nowrap;
  }

  :deep(tr:nth-child(even)) {
    background: #fafafa;
  }

  :deep(tr:hover) {
    background: #f5f7fa;
  }

  /* Markdown 标题样式 */
  :deep(h1), :deep(h2), :deep(h3), :deep(h4) {
    margin: 12px 0 8px;
    color: #303133;
  }

  :deep(h3) {
    font-size: 15px;
    font-weight: 600;
    border-left: 3px solid #409eff;
    padding-left: 8px;
  }

  :deep(h4) {
    font-size: 14px;
    font-weight: 600;
  }

  /* 代码块样式 */
  :deep(pre) {
    background: #f5f7fa;
    padding: 10px 12px;
    border-radius: 6px;
    overflow-x: auto;
    font-size: 12px;
    margin: 8px 0;
  }

  :deep(code) {
    font-family: 'Courier New', monospace;
    background: #f5f7fa;
    padding: 2px 4px;
    border-radius: 3px;
    font-size: 12px;
  }
}

.time {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 4px;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 768px) {
  .chat-bubble {
    gap: 8px;
  }

  .content-wrapper {
    max-width: 80%;
  }

  .content {
    padding: 8px 12px;
    font-size: 13px;
  }
}
</style>
