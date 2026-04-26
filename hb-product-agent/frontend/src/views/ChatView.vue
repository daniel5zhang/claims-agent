<template>
  <div class="chat-view">
    <!-- 会话列表侧边栏 -->
    <div class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-header">
        <el-button type="primary" size="small" @click="onNewSession" style="width: 100%">
          + 新建会话
        </el-button>
        <el-button size="small" @click="sidebarCollapsed = true" class="collapse-btn">
          &lt;
        </el-button>
      </div>
      <div class="session-list">
        <div
          v-for="s in sessions"
          :key="s.session_id"
          class="session-item"
          :class="{ active: s.session_id === sessionId }"
          @click="onSwitchSession(s)"
        >
          <div class="session-title">{{ s.title || '未命名会话' }}</div>
          <div class="session-time">{{ formatTime(s.update_time || s.create_time) }}</div>
          <el-button
            class="session-delete"
            size="small"
            :icon="Delete"
            text
            @click.stop="onDeleteSession(s.session_id)"
          />
        </div>
        <div v-if="sessions.length === 0" class="no-sessions">
          暂无会话
        </div>
      </div>
    </div>
    <!-- 侧边栏展开按钮 -->
    <div v-if="sidebarCollapsed" class="sidebar-toggle" @click="sidebarCollapsed = false">
      &gt;
    </div>

    <!-- 主内容区 -->
    <div class="chat-main">
    <!-- 头部 -->
    <div class="chat-header">
      <h2>产品方案助手</h2>
      <p class="subtitle">输入客户需求，快速生成健管服务方案与报价</p>
    </div>

    <!-- 对话区域 -->
    <div class="chat-messages" ref="messagesRef">
      <div v-if="messages.length === 0" class="welcome">
        <div class="welcome-card">
          <h3>我可以帮您：</h3>
          <ul>
            <li>将客户碎片化需求转化为专业方案</li>
            <li>推荐合适的健管服务组合与报价</li>
            <li>生成可直接提交的结构化产品方案</li>
            <li>导出 Word 服务手册与 Excel 报价单</li>
          </ul>
          <div class="quick-starts">
            <el-button
              v-for="q in quickStarts"
              :key="q"
              size="small"
              @click="sendQuick(q)"
            >
              {{ q }}
            </el-button>
          </div>
        </div>
      </div>

      <template v-for="(msg, idx) in messages" :key="idx">
        <ChatBubble :message="msg" />
        <!-- 下载卡片：Excel/手册生成后显示 -->
        <div v-if="msg._downloads" class="download-cards">
          <div v-for="d in msg._downloads" :key="d.type" class="download-card-item">
            <el-icon :size="20"><Document /></el-icon>
            <span class="download-label">{{ d.label }}</span>
            <el-button size="small" type="primary" @click="d.action()">下载</el-button>
          </div>
        </div>
      </template>

      <!-- 加载中 -->
      <div v-if="loading" class="loading-indicator">
        <div class="loading-animation">
          <span class="dot"></span>
          <span class="dot"></span>
          <span class="dot"></span>
        </div>
        <div class="loading-text">
          <p class="loading-main">{{ loadingText }}</p>
          <p class="loading-sub">{{ loadingSubText }}</p>
        </div>
      </div>
    </div>


    <!-- 输入区域 -->
    <div class="chat-input-area">
      <div class="input-box">
        <el-input
          v-model="inputMessage"
          type="textarea"
          :rows="2"
          placeholder="输入您的需求..."
          @keydown.enter.prevent="handleEnter"
        />
        <el-button
          type="primary"
          :loading="loading"
          @click="sendMessage"
          class="send-btn"
        >
          发送
        </el-button>
      </div>
    </div>
    </div><!-- /chat-main -->
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { Document, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ChatBubble from '../components/ChatBubble.vue'
import { sendMessageAsync as apiSendMessageAsync, getTaskStatus, getHistory, getSessions, deleteSession } from '../api/chat'
import { generateManual, downloadManual } from '../api/manual'
import { generateExcel, downloadExcel } from '../api/excel'

const messages = ref([])
const inputMessage = ref('')
const loading = ref(false)
const loadingText = ref('Agent 正在思考...')
const loadingSubText = ref('')
const sessionId = ref(localStorage.getItem('agent_session_id') || '')
const messagesRef = ref(null)
const currentScheme = ref(null)
const sessions = ref([])
const sidebarCollapsed = ref(false)
let loadingTimer = null

const loadingStages = [
  { text: '正在理解您的需求...', sub: '大模型分析中，请稍候' },
  { text: '正在匹配服务素材...', sub: '从素材库中筛选合适的服务' },
  { text: '正在生成方案...', sub: '构建结构化产品方案' },
  { text: '正在优化回复...', sub: '即将完成' },
]

function startLoadingAnimation() {
  let stage = 0
  loadingText.value = loadingStages[0].text
  loadingSubText.value = loadingStages[0].sub
  loadingTimer = setInterval(() => {
    stage = (stage + 1) % loadingStages.length
    loadingText.value = loadingStages[stage].text
    loadingSubText.value = loadingStages[stage].sub
  }, 5000)
}

function stopLoadingAnimation() {
  if (loadingTimer) {
    clearInterval(loadingTimer)
    loadingTimer = null
  }
}

const quickStarts = [
  '银行渠道小微企业贷健管方案，预算50-60元',
  '车险随车健管服务，预算10-30元/人',
  '职工家庭防癌抗癌保障卡，预算100-150元',
  '重疾绿通升级版，含门诊绿通和住院护工',
  '企业员工健管福利，人均预算50-100元',
  '癌症早筛+重疾门诊+专家会诊组合方案',
  '设计1元引流到30元转化的分层方案',
  '看看素材库里有哪些服务',
]

onMounted(() => {
  loadSessionList()
  if (sessionId.value) {
    loadHistory()
  }
})

async function loadHistory() {
  try {
    const res = await getHistory(sessionId.value)
    if (res.data && res.data.messages) {
      messages.value = res.data.messages
      scrollToBottom()
    }
    // 恢复方案状态（含已确认方案的 excelId / manualId）
    if (res.data && res.data.scheme) {
      const s = res.data.scheme
      currentScheme.value = {
        id: s.id,
        conversation_id: s.conversation_id,
        scheme_name: s.scheme_name,
        scene: s.scene,
        target_group: s.target_group,
        service_list: s.service_list || [],
        total_cost: s.total_cost || 0,
        total_quote: s.total_quote || 0,
        status: s.status,
        schemes: s.schemes || [],
        excelId: s.excelId || null,
        excelVersion: s.excelVersion || 1,
        manualId: s.manualId || null,
        manualVersion: s.manualVersion || 1,
      }
      // 如果已有 excelId/manualId，推下载卡片
      if (s.excelId || s.manualId) {
        const downloads = []
        if (s.excelId) {
          const ver = s.excelVersion || 1
          downloads.push({
            type: 'excel',
            label: `📥 Excel报价单_v${ver}.xlsx`,
            action: () => downloadExcel(s.excelId),
          })
        }
        if (s.manualId) {
          const ver = s.manualVersion || 1
          downloads.push({
            type: 'manual',
            label: `📥 服务手册_v${ver}.docx`,
            action: () => downloadManual(s.manualId),
          })
        }
        if (downloads.length > 0) {
          messages.value.push({
            role: 'assistant',
            content: '以下文件已生成，点击按钮即可下载。',
            _downloads: downloads,
          })
        }
      }
    }
  } catch (e) {
    console.log('加载历史失败', e)
  }
}

// 加载会话列表
async function loadSessionList() {
  try {
    const res = await getSessions()
    if (res.data) {
      sessions.value = res.data
    }
  } catch (e) {
    console.log('加载会话列表失败', e)
  }
}

// 新建会话
function onNewSession() {
  sessionId.value = ''
  localStorage.removeItem('agent_session_id')
  messages.value = []
  currentScheme.value = null
}

// 切换会话
async function onSwitchSession(s) {
  if (s.session_id === sessionId.value) return
  sessionId.value = s.session_id
  localStorage.setItem('agent_session_id', s.session_id)
  messages.value = []
  currentScheme.value = null
  await loadHistory()
}

// 删除会话
async function onDeleteSession(sid) {
  try {
    await ElMessageBox.confirm('确定删除此会话？删除后不可恢复。', '删除会话', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await deleteSession(sid)
    ElMessage.success('会话已删除')
    if (sid === sessionId.value) {
      onNewSession()
    }
    await loadSessionList()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 格式化时间
function formatTime(t) {
  if (!t) return ''
  const d = new Date(t)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

async function pollTask(taskId, maxAttempts = 300) {
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(r => setTimeout(r, 1500))
    const res = await getTaskStatus(taskId)
    const task = res.data
    if (task.status === 'completed') {
      return task.result
    }
    if (task.status === 'failed') {
      throw new Error(task.error || '任务处理失败')
    }
    if (task.status === 'timeout') {
      throw new Error('任务处理超时，请稍后重试')
    }
    // pending: 继续轮询（显示已等待时间）
  }
  throw new Error('轮询超时（已等待7.5分钟），请刷新页面查看结果')
}

async function sendMessage() {
  const text = inputMessage.value.trim()
  if (!text || loading.value) return

  // 用户消息
  messages.value.push({ role: 'user', content: text })
  inputMessage.value = ''
  loading.value = true
  startLoadingAnimation()
  scrollToBottom()

  try {
    // 1. 提交异步任务
    const submitRes = await apiSendMessageAsync(sessionId.value, text)
    const taskId = submitRes.data.task_id

    // 2. 轮询获取结果
    const data = await pollTask(taskId)

    // 保存 sessionId
    if (data.session_id) {
      sessionId.value = data.session_id
      localStorage.setItem('agent_session_id', data.session_id)
      // 刷新会话列表（新会话会出现在列表中）
      loadSessionList()
    }

    // 添加助手回复
    const assistantMsg = { ...data.message }
    if (data.scheme) {
      console.log('[sendMessage] 收到 scheme:', JSON.stringify(data.scheme, null, 2))
      currentScheme.value = data.scheme
      // 方案确认后，自动生成 Excel 报价单 和 Word 服务手册
      if (data.scheme.status === 'confirmed') {
        if (!data.scheme.excelId) {
          console.log('[sendMessage] 触发自动生成 Excel, scheme_id=', data.scheme.id)
          autoGenerateExcel()
        }
        if (!data.scheme.manualId) {
          console.log('[sendMessage] 触发自动生成 Word 手册, scheme_id=', data.scheme.id)
          autoGenerateManual()
        }
      }
    }
    messages.value.push(assistantMsg)

    // 检测用户手动触发文件生成意图（备用，对话触发）
    if (data.scheme && data.scheme.status === 'confirmed') {
      if (/生成.*手册|服务手册|word/i.test(text)) {
        console.log('[sendMessage] 检测到手动生成手册意图')
        await autoGenerateManual()
      } else if (/生成.*excel|报价单|excel/i.test(text)) {
        console.log('[sendMessage] 检测到手动生成Excel意图')
        await autoGenerateExcel()
      }
    }

    scrollToBottom()
  } catch (e) {
    ElMessage.error(e.message || '发送失败')
  } finally {
    loading.value = false
    stopLoadingAnimation()
  }
}

function sendQuick(text) {
  inputMessage.value = text
  sendMessage()
}

function handleEnter(e) {
  if (!e.shiftKey) {
    sendMessage()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}


// 自动生成 Excel 报价单（确认后自动调用，推下载卡片到聊天流）
async function autoGenerateExcel() {
  if (!currentScheme.value?.id) {
    console.warn('[autoGenerateExcel] currentScheme.value.id 不存在，跳过')
    return
  }
  console.log('[autoGenerateExcel] 开始生成 Excel, scheme_id=', currentScheme.value.id)
  try {
    const excelRes = await generateExcel(currentScheme.value.id)
    const excelData = excelRes.data
    console.log('[autoGenerateExcel] Excel 生成成功:', excelData)
    const ver = excelData.version || 1
    currentScheme.value.excelId = excelData.excel_id
    currentScheme.value.excelVersion = ver
    messages.value.push({
      role: 'assistant',
      content: 'Excel报价单已生成，点击下方按钮即可下载。',
      _downloads: [{
        type: 'excel',
        label: `📥 Excel报价单_v${ver}.xlsx`,
        action: () => downloadExcel(currentScheme.value.excelId),
      }],
    })
    scrollToBottom()
  } catch (excelErr) {
    console.error('[autoGenerateExcel] Excel生成失败:', excelErr)
    messages.value.push({
      role: 'assistant',
      content: 'Excel报价单自动生成失败，请发送「生成Excel报价单」来手动重试。',
    })
    scrollToBottom()
  }
}


// 自动生成服务手册（通过对话触发，推下载卡片到聊天流）
async function autoGenerateManual() {
  if (!currentScheme.value?.id || currentScheme.value.status !== 'confirmed') return
  console.log('[autoGenerateManual] 开始生成, scheme_id=', currentScheme.value.id)
  try {
    const res = await generateManual(currentScheme.value.id)
    const data = res.data
    const ver = data.version || 1
    currentScheme.value.manualId = data.manual_id
    currentScheme.value.manualVersion = ver
    messages.value.push({
      role: 'assistant',
      content: '服务手册已生成，点击下方按钮即可下载。',
      _downloads: [{
        type: 'manual',
        label: `📥 服务手册_v${ver}.docx`,
        action: () => downloadManual(currentScheme.value.manualId),
      }],
    })
    scrollToBottom()
  } catch (e) {
    console.error('[autoGenerateManual] 失败:', e)
    messages.value.push({
      role: 'assistant',
      content: '服务手册生成失败，请稍后重试。',
    })
    scrollToBottom()
  }
}

</script>

<style scoped lang="scss">
.chat-view {
  display: flex;
  flex-direction: row;
  height: 100vh;
  background: #fff;
}

// 侧边栏
.sidebar {
  width: 260px;
  min-width: 260px;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
  background: #f9fafb;
  transition: all 0.2s ease;

  &.collapsed {
    width: 0;
    min-width: 0;
    overflow: hidden;
    border-right: none;
  }
}

.sidebar-header {
  padding: 12px;
  display: flex;
  gap: 8px;
  border-bottom: 1px solid #e8e8e8;

  .collapse-btn {
    flex-shrink: 0;
  }
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.session-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  position: relative;
  margin-bottom: 4px;
  transition: background 0.15s;

  &:hover {
    background: #eef2ff;
  }

  &.active {
    background: #e8f0fe;
    border-left: 3px solid #409eff;
  }

  .session-title {
    flex: 1;
    font-size: 13px;
    color: #333;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    padding-right: 4px;
  }

  .session-time {
    width: 100%;
    font-size: 11px;
    color: #999;
    margin-top: 2px;
  }

  .session-delete {
    position: absolute;
    right: 4px;
    top: 4px;
    opacity: 0;
    transition: opacity 0.15s;
  }

  &:hover .session-delete {
    opacity: 1;
  }
}

.no-sessions {
  text-align: center;
  color: #999;
  font-size: 13px;
  padding: 24px 0;
}

.sidebar-toggle {
  width: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f0f0;
  cursor: pointer;
  font-size: 14px;
  color: #666;
  border-right: 1px solid #e8e8e8;

  &:hover {
    background: #e8e8e8;
  }
}

// 主内容区
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  max-width: 900px;
  margin: 0 auto;
  min-width: 0;
}

.chat-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e4e7ed;
  background: linear-gradient(135deg, #003366 0%, #0066cc 100%);
  color: #fff;

  h2 {
    margin: 0;
    font-size: 18px;
  }

  .subtitle {
    margin: 4px 0 0;
    font-size: 13px;
    opacity: 0.85;
  }
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  background: #f5f7fa;
}

.welcome {
  display: flex;
  justify-content: center;
  margin-top: 40px;
}

.welcome-card {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  max-width: 500px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);

  h3 {
    margin-bottom: 12px;
    font-size: 16px;
    color: #303133;
  }

  ul {
    margin: 0 0 16px 18px;
    color: #606266;
    font-size: 14px;
    line-height: 2;
  }
}

.quick-starts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;

  .el-button {
    margin: 0;
  }
}

.loading-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #fff;
  border-radius: 12px;
  margin: 8px 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.loading-animation {
  display: flex;
  gap: 4px;
  align-items: center;
}

.loading-animation .dot {
  width: 8px;
  height: 8px;
  background: #409eff;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-animation .dot:nth-child(1) {
  animation-delay: -0.32s;
}

.loading-animation .dot:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}

.loading-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.loading-main {
  color: #303133;
  font-size: 14px;
  font-weight: 500;
  margin: 0;
}

.loading-sub {
  color: #909399;
  font-size: 12px;
  margin: 0;
}

/* 下载卡片（内嵌聊天流） */
.download-cards {
  margin: 8px 40px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.download-card-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: #f0f9ff;
  border: 1px solid #d0e8ff;
  border-radius: 8px;
  font-size: 13px;
  color: #303133;

  .download-label {
    flex: 1;
    font-weight: 500;
  }
}

.chat-input-area {
  padding: 12px 20px;
  border-top: 1px solid #e4e7ed;
  background: #fff;
}

.input-box {
  display: flex;
  gap: 12px;
  align-items: flex-end;

  .el-textarea {
    flex: 1;
  }

  .send-btn {
    margin-bottom: 2px;
  }
}

/* 移动端适配 */
@media (max-width: 768px) {
  .chat-view {
    max-width: 100%;
  }

  .chat-header {
    padding: 12px 16px;

    h2 {
      font-size: 16px;
    }
  }

  .chat-messages {
    padding: 12px 16px;
  }

  .scheme-action-bar {
    padding: 10px 16px;
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;

    .action-bar-btns {
      width: 100%;
      justify-content: flex-start;
    }
  }

  .chat-input-area {
    padding: 10px 16px;
  }
}
</style>
