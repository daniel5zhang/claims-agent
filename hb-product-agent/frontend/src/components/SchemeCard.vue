<template>
  <div class="scheme-card-wrapper">
    <el-card class="scheme-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="title">
            <el-icon><Document /></el-icon>
            生成方案
          </span>
          <el-tag size="small" :type="statusType">{{ statusText }}</el-tag>
        </div>
      </template>

      <div v-if="scheme && scheme.service_list" class="scheme-summary">
        <div class="scheme-name">{{ scheme.scheme_name || '未命名方案' }}</div>

        <!-- 关键信息卡片 -->
        <div class="scheme-key-info">
          <div class="info-row">
            <span class="info-label">总成本</span>
            <span class="info-value cost">{{ scheme.total_cost || '-' }} <small>元/人/年</small></span>
          </div>
          <div class="info-row">
            <span class="info-label">总报价</span>
            <span class="info-value quote">{{ scheme.total_quote || '-' }} <small>元/人/年</small></span>
          </div>
          <div class="info-row">
            <span class="info-label">服务项</span>
            <span class="info-value">{{ scheme.service_list?.length || 0 }} <small>项</small></span>
          </div>
        </div>

        <!-- 定价分析面板 -->
        <PricingPanel :pricing="scheme.pricing" />

        <!-- 引导文案（对话交互，无需按钮） -->
        <div class="scheme-guide">
          <template v-if="scheme.status === 'draft'">
            <p class="guide-text">回复 <strong>「确认」</strong> 锁定此方案并自动生成Excel报价单</p>
            <p class="guide-text sub">如需调整，直接描述修改需求即可（如"把心理咨询换成视频问诊"）</p>
          </template>
          <template v-else-if="scheme.status === 'confirmed'">
            <p class="guide-text confirmed">方案已确认</p>
            <p class="guide-text sub">回复 <strong>「生成服务手册」</strong> 下载Word服务手册</p>
          </template>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Document } from '@element-plus/icons-vue'
import PricingPanel from './PricingPanel.vue'


const props = defineProps({
  scheme: {
    type: Object,
    default: () => ({})
  }
})

const statusText = computed(() => {
  const map = { draft: '草稿', confirmed: '已确认' }
  return map[props.scheme?.status] || props.scheme?.status
})

const statusType = computed(() => {
  const map = { draft: 'info', confirmed: 'success' }
  return map[props.scheme?.status] || 'info'
})


</script>

<style scoped lang="scss">
.scheme-card-wrapper {
  margin: 12px 40px;
  animation: slideUp 0.4s ease;
}

.scheme-card {
  border-left: 4px solid #409eff;

  :deep(.el-card__header) {
    padding: 12px 16px;
  }

  :deep(.el-card__body) {
    padding: 16px;
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;

  .title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
    color: #303133;
  }
}

.scheme-summary {
  .scheme-name {
    font-size: 16px;
    font-weight: 600;
    color: #303133;
    margin-bottom: 12px;
  }

  .scheme-key-info {
    display: flex;
    gap: 16px;
    margin-bottom: 14px;
    padding: 12px;
    background: #f5f7fa;
    border-radius: 8px;

    .info-row {
      display: flex;
      flex-direction: column;
      align-items: center;
      flex: 1;
      text-align: center;
    }

    .info-label {
      font-size: 12px;
      color: #909399;
      margin-bottom: 4px;
    }

    .info-value {
      font-size: 16px;
      font-weight: 600;
      color: #303133;

      small {
        font-size: 11px;
        font-weight: 400;
        color: #909399;
      }

      &.cost {
        color: #f56c6c;
      }

      &.quote {
        color: #67c23a;
      }
    }
  }
}

.scheme-guide {
  margin-top: 14px;
  padding: 10px 14px;
  background: #f0f9ff;
  border-radius: 6px;
  border: 1px solid #d0e8ff;

  .guide-text {
    margin: 0;
    font-size: 13px;
    color: #606266;
    line-height: 1.8;

    strong {
      color: #409eff;
      background: #ecf5ff;
      padding: 1px 6px;
      border-radius: 3px;
    }

    &.confirmed {
      color: #67c23a;
    }

    &.sub {
      font-size: 12px;
      color: #909399;
    }
  }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 768px) {
  .scheme-card-wrapper {
    margin: 12px 16px;
  }

  .price-row {
    flex-direction: column;
    gap: 6px;
  }
}
</style>
