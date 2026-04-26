<template>
  <div class="pricing-panel" v-if="hasPricingData">
    <div class="pricing-header">
      <span class="pricing-label">定价分析</span>
      <el-tag v-if="pricingMethod" size="small" type="info" effect="plain">
        {{ pricingMethodLabel }}
      </el-tag>
    </div>

    <!-- 引擎 vs LLM 对比 -->
    <div class="pricing-compare" v-if="showCompare">
      <div class="compare-row">
        <div class="compare-item">
          <span class="compare-label">引擎基准价</span>
          <span class="compare-value">{{ formatPrice(pricing.engine_total_quote) }}</span>
        </div>
        <span class="compare-arrow">→</span>
        <div class="compare-item">
          <span class="compare-label">LLM最终报价</span>
          <span class="compare-value llm">
            {{ formatPrice(pricing.llm_total_quote || pricing.final_total_quote) }}
          </span>
        </div>
        <div class="deviation-badge" :class="deviationClass" v-if="deviation !== null">
          {{ deviation >= 0 ? '+' : '' }}{{ (deviation * 100).toFixed(1) }}%
        </div>
      </div>
      <div class="compare-row cost-row" v-if="pricing.engine_total_cost">
        <span class="compare-label">引擎成本</span>
        <span class="compare-value cost">{{ formatPrice(pricing.engine_total_cost) }}</span>
        <span class="margin-label" v-if="pricing.final_total_quote && pricing.engine_total_cost">
          利润率 {{ marginRate }}
        </span>
      </div>
    </div>

    <!-- 定价逻辑摘要 -->
    <div class="pricing-logic" v-if="pricing.logic && pricing.logic.description">
      <div class="logic-title">定价逻辑</div>
      <div class="logic-text">{{ pricing.logic.description }}</div>
      <div class="logic-meta" v-if="pricing.logic.confidence">
        置信度: {{ (pricing.logic.confidence * 100).toFixed(0) }}%
      </div>
    </div>

    <!-- 方法标签 -->
    <div class="pricing-method-hint" v-if="!pricing.logic && pricingMethod">
      <span>{{ pricingMethodLabel }} · 置信度 {{ confidencePct }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  pricing: {
    type: Object,
    default: null,
  },
})

const hasPricingData = computed(() => {
  return props.pricing && (
    props.pricing.engine_total_quote ||
    props.pricing.engine_total_cost ||
    props.pricing.logic ||
    props.pricing.method
  )
})

const pricingMethod = computed(() => props.pricing?.method || props.pricing?.logic?.method || null)

const pricingMethodLabel = computed(() => {
  const map = {
    cost_plus: '成本加成法',
    market_benchmark: '市场对标法',
    hybrid: '混合定价法',
    tiered: '阶梯定价法',
    llm_hybrid: 'LLM混合定价',
  }
  return map[pricingMethod.value] || pricingMethod.value || '未知'
})

const confidencePct = computed(() => {
  const c = props.pricing?.logic?.confidence
  return c !== undefined && c !== null ? `${(c * 100).toFixed(0)}%` : '—'
})

const showCompare = computed(() => {
  return props.pricing?.engine_total_quote && (
    props.pricing?.llm_total_quote || props.pricing?.final_total_quote
  )
})

const deviation = computed(() => {
  const engine = props.pricing?.engine_total_quote
  const llm = props.pricing?.llm_total_quote || props.pricing?.final_total_quote
  if (!engine || !llm || engine === 0) return null
  return (llm - engine) / engine
})

const deviationClass = computed(() => {
  if (deviation.value === null) return ''
  const abs = Math.abs(deviation.value)
  if (abs <= 0.15) return 'dev-ok'
  if (abs <= 0.30) return 'dev-warn'
  return 'dev-error'
})

const marginRate = computed(() => {
  const cost = props.pricing?.engine_total_cost
  const quote = props.pricing?.final_total_quote || props.pricing?.llm_total_quote
  if (!cost || !quote || cost === 0) return '—'
  return ((quote - cost) / cost * 100).toFixed(1) + '%'
})

function formatPrice(val) {
  if (val === null || val === undefined) return '—'
  return Number(val).toFixed(2) + ' 元'
}
</script>

<style scoped>
.pricing-panel {
  margin-top: 12px;
  padding: 12px 16px;
  background: #f7f8fc;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  font-size: 13px;
}

.pricing-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.pricing-label {
  font-weight: 600;
  color: #303133;
  font-size: 14px;
}

.pricing-compare {
  margin-bottom: 10px;
}

.compare-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}

.compare-item {
  display: flex;
  flex-direction: column;
}

.compare-label {
  color: #909399;
  font-size: 12px;
}

.compare-value {
  font-weight: 600;
  color: #409eff;
  font-size: 15px;
}

.compare-value.llm {
  color: #67c23a;
}

.compare-value.cost {
  color: #909399;
  font-size: 13px;
}

.compare-arrow {
  color: #c0c4cc;
  font-size: 16px;
  margin-top: 8px;
}

.deviation-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  margin-left: 4px;
}

.dev-ok {
  color: #67c23a;
  background: #f0f9eb;
}

.dev-warn {
  color: #e6a23c;
  background: #fdf6ec;
}

.dev-error {
  color: #f56c6c;
  background: #fef0f0;
}

.margin-label {
  color: #e6a23c;
  font-size: 12px;
  margin-left: 8px;
}

.pricing-logic {
  background: #fff;
  padding: 10px 12px;
  border-radius: 6px;
  margin-top: 8px;
}

.logic-title {
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}

.logic-text {
  color: #606266;
  line-height: 1.6;
  font-size: 13px;
}

.logic-meta {
  color: #c0c4cc;
  font-size: 11px;
  margin-top: 6px;
}

.pricing-method-hint {
  color: #909399;
  font-size: 12px;
}
</style>
