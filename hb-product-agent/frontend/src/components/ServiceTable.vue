<template>
  <div class="service-table">
    <el-table
      :data="services"
      size="small"
      :border="true"
      :stripe="true"
      style="width: 100%"
    >
      <el-table-column type="index" label="序号" width="55" align="center" />
      <el-table-column prop="name" label="服务项目" min-width="140" show-overflow-tooltip />
      <el-table-column prop="times" label="服务次数" width="100" align="center" />
      <el-table-column prop="condition" label="启动条件" min-width="120" show-overflow-tooltip />
      <el-table-column prop="cost_price" label="成本价（元）" width="100" align="right">
        <template #default="{ row }">
          <span class="cost">{{ row.cost_price || row.cost || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="quote_price" label="报价（元）" width="100" align="right">
        <template #default="{ row }">
          <span class="quote">{{ row.quote_price || row.price || row.quote || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="remark" label="备注" min-width="100" show-overflow-tooltip />
    </el-table>
  </div>
</template>

<script setup>
defineProps({
  services: {
    type: Array,
    default: () => []
  }
})
</script>

<style scoped lang="scss">
.service-table {
  .price {
    color: #f56c6c;
    font-weight: 600;
  }

  :deep(.el-table) {
    font-size: 13px;
  }
}

@media (max-width: 768px) {
  .service-table {
    :deep(.el-table) {
      font-size: 12px;
    }
  }
}
</style>
