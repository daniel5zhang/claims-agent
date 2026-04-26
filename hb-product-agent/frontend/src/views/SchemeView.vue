<template>
  <div class="scheme-view">
    <el-page-header @back="goBack" title="方案详情" />

    <div v-if="scheme" class="scheme-content">
      <el-card class="scheme-card">
        <template #header>
          <div class="scheme-header">
            <h3>{{ scheme.scheme_name || '未命名方案' }}</h3>
            <el-tag :type="statusType">{{ statusText }}</el-tag>
          </div>
        </template>

        <div class="scheme-info">
          <p v-if="scheme.total_cost">
            <strong>预估成本：</strong> {{ scheme.total_cost }} 元/人/年
          </p>
          <p v-if="scheme.total_quote">
            <strong>预估报价：</strong> {{ scheme.total_quote }} 元/人/年
          </p>
        </div>

        <ServiceTable :services="scheme.service_list || []" />

        <div class="scheme-actions">
          <el-button
            v-if="scheme.status === 'draft'"
            type="primary"
            @click="onConfirm"
          >
            确认方案
          </el-button>
          <el-button
            v-if="scheme.status === 'confirmed'"
            type="success"
            @click="onGenerateManual"
            :loading="generatingManual"
          >
            生成服务手册
          </el-button>
          <el-button
            v-if="manualId"
            type="info"
            @click="onDownloadManual"
          >
            下载服务手册
          </el-button>
          <el-button
            v-if="scheme.status === 'confirmed'"
            @click="onCancelConfirm"
          >
            取消确认
          </el-button>
        </div>
      </el-card>
    </div>

    <el-empty v-else description="方案不存在或已删除" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import ServiceTable from '../components/ServiceTable.vue'
import { getScheme, confirmScheme } from '../api/scheme'
import { generateManual, downloadManual } from '../api/manual'

const route = useRoute()
const router = useRouter()

const scheme = ref(null)
const loading = ref(false)
const generatingManual = ref(false)
const manualId = ref(null)

const statusText = computed(() => {
  const map = { draft: '草稿', confirmed: '已确认' }
  return map[scheme.value?.status] || scheme.value?.status
})

const statusType = computed(() => {
  const map = { draft: 'info', confirmed: 'success' }
  return map[scheme.value?.status] || 'info'
})

onMounted(() => {
  const schemeId = route.params.schemeId
  if (schemeId) {
    loadScheme(schemeId)
  }
})

async function loadScheme(schemeId) {
  loading.value = true
  try {
    const res = await getScheme(schemeId)
    scheme.value = res.data
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function goBack() {
  router.push('/chat')
}

async function onConfirm() {
  try {
    await ElMessageBox.confirm('确认后将锁定方案，可以生成服务手册', '确认方案')
    await confirmScheme(scheme.value.id, true)
    scheme.value.status = 'confirmed'
    ElMessage.success('方案已确认')
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.message || '确认失败')
    }
  }
}

async function onCancelConfirm() {
  try {
    await confirmScheme(scheme.value.id, false)
    scheme.value.status = 'draft'
    ElMessage.success('已取消确认')
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  }
}

async function onGenerateManual() {
  generatingManual.value = true
  try {
    const res = await generateManual(scheme.value.id)
    manualId.value = res.data.manual_id
    ElMessage.success('服务手册生成成功')
  } catch (e) {
    ElMessage.error(e.message || '生成失败')
  } finally {
    generatingManual.value = false
  }
}

function onDownloadManual() {
  if (manualId.value) {
    downloadManual(manualId.value)
  }
}
</script>

<style scoped lang="scss">
.scheme-view {
  max-width: 900px;
  margin: 0 auto;
  padding: 20px;
}

.scheme-content {
  margin-top: 20px;
}

.scheme-header {
  display: flex;
  justify-content: space-between;
  align-items: center;

  h3 {
    margin: 0;
  }
}

.scheme-info {
  margin-bottom: 16px;

  p {
    margin: 6px 0;
    font-size: 14px;
  }
}

.scheme-actions {
  margin-top: 20px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

@media (max-width: 768px) {
  .scheme-view {
    padding: 12px;
  }
}
</style>
