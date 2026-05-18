<template>
  <div class="detail" v-if="c">
    <div class="header">
      <h2>{{ c.case_no }}</h2>
      <div class="meta">
        <span>{{ c.insured_name }}</span> | <span>{{ c.id_number }}</span> |
        <span>诊断: {{ c.diagnosis || '待OCR提取' }}</span> |
        <span>{{ c.report_date?.slice(0,10) }}</span>
        <span :class="'tag tag-'+c.status">{{ labels[c.status]||c.status }}</span>
      </div>
      <div class="policies" v-if="c.policy_links?.length">
        保单:
        <button v-for="pl in c.policy_links" :key="pl.id" :class="{active:activePolicy===pl.id}" @click="activePolicy=pl.id">{{pl.product_name||pl.policy_no}} {{pl.policy_no?.slice(-8)}}</button>
      </div>
    </div>
    <div class="body">
      <div class="tabs">
        <button :class="{active:tab==='progress'}" @click="tab='progress'">执行进度</button>
        <button :class="{active:tab==='rules'}" @click="tab='rules'">规则矩阵</button>
        <button :class="{active:tab==='attachments'}" @click="tab='attachments'">附件</button>
        <button :class="{active:tab==='report'}" @click="tab='report'">审核报告</button>
      </div>
      <div class="content">
        <div v-if="tab==='progress'" class="progress">
          <div class="timeline"><div v-for="p in phases" :key="p.key" class="phase"><span :class="'dot '+p.status"></span><div class="info"><strong>{{p.key}}: {{p.name}}</strong><div class="detail" v-if="p.detail">{{p.detail}}</div></div><span class="time" v-if="p.duration">{{p.duration}}</span></div></div>
          <div v-if="wsEvents.length" class="events"><h4>实时事件</h4><div v-for="(e,i) in wsEvents" :key="i" class="event">[{{e.event}}] {{e.message||e.reason||''}}</div></div>
        </div>
        <div v-if="tab==='rules'" class="matrix">
          <div v-for="(rules,layer) in ruleLayers" :key="layer" class="layer"><h4>层{{layer}}: {{layerNames[layer]}}</h4>
            <div v-for="r in rules" :key="r.code" class="rule"><span :class="'dot '+r.result">●</span><span class="code">{{r.code}}</span><span class="name">{{r.name}}</span><span :class="'result '+r.result">{{statusLabel(r.result)}}</span><span class="reason" v-if="r.reason">{{r.reason}}</span><button v-if="r.evidences" class="lnk" @click="showEvidence=r">查看依据</button></div>
          </div>
          <EvidenceViewer v-if="showEvidence" :evidences="showEvidence.evidences||[]" />
        </div>
        <div v-if="tab==='attachments'"><AttachmentPreview :attachments="c.attachments||[]" /></div>
        <div v-if="tab==='report'" class="report">
          <div class="section"><h3>一、案件基础信息</h3><p>案件号: {{c.case_no}} | 出险人: {{c.insured_name}} | 诊断: {{c.diagnosis}} | 理赔模式: {{c.claim_mode}} | 优先级: {{c.priority}}</p></div>
          <div class="section"><h3>二、保单列表</h3><ul><li v-for="pl in c.policy_links||[]" :key="pl.id">{{pl.product_name||pl.policy_no}} ({{pl.source}})</li></ul></div>
          <div class="section"><h3>三、附件清单</h3><ul><li v-for="a in c.attachments||[]" :key="a.id">{{a.file_name}} ({{a.attachment_type||'未分类'}})</li></ul></div>
          <div class="section"><h3>四、Agent 执行过程</h3><div v-for="p in phases" :key="p.key"><strong>{{p.key}} {{p.name}}:</strong> {{p.status}} {{p.duration?'('+p.duration+')':''}}</div></div>
          <div class="section"><h3>五、适应症审核要点</h3><p>按药品分组</p></div>
          <div class="section"><h3>六、理算明细</h3><p>赔付金额</p></div>
          <div class="section"><h3>七、人工介入记录</h3><div v-for="i in interventions" :key="i.id">{{i.time}} {{i.operator}}: {{i.opinion}}</div></div>
          <div class="section"><h3>八、时效信息</h3><p>报案: {{c.report_date}} | 创建: {{c.created_at}}</p></div>
          <div class="section"><h3>九、最终决策</h3><p :class="'decision '+finalResult">{{finalResult||'待审核'}}</p><p v-if="finalAmount">赔付: ¥{{finalAmount.toLocaleString()}}</p></div>
        </div>
      </div>
    </div>
    <div class="actions">
      <button class="btn primary" @click="runAudit" v-if="c.status==='pending'">执行智能审核</button>
      <button class="btn" @click="cancel" v-if="c.status!=='cancelled'&&c.status!=='completed'">撤销</button>
      <button class="btn" @click="showIntervene=!showIntervene">💬 人工介入</button>
    </div>
    <div v-if="showIntervene" class="drawer-overlay" @click.self="showIntervene=false">
      <div class="drawer"><h3>💬 人工介入</h3><textarea v-model="interveneText" placeholder="输入引导指令" rows="4"></textarea>
        <div class="btns"><button class="btn primary" @click="doIntervene('continue')">发送并继续</button><button class="btn" @click="doIntervene('pause')">暂停</button><button class="btn" @click="doIntervene('override')">覆盖</button></div>
      </div>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'; import { useRoute } from 'vue-router'; import { api } from '../api'; import { useWebSocket } from '../composables/useWebSocket'
import AttachmentPreview from '../components/AttachmentPreview.vue'; import EvidenceViewer from '../components/EvidenceViewer.vue'
const route = useRoute(); const c = ref(null); const tab = ref('progress'); const activePolicy = ref(null)
const showIntervene = ref(false); const showEvidence = ref(null); const interveneText = ref('')
const interventions = ref([]); const finalResult = ref(null); const finalAmount = ref(null)
const labels = {pending:'待处理',running:'审核中',completed:'已完成',supplement_required:'待补材',manual_review:'转人工',error:'异常',cancelled:'已撤销'}
const phases = ref([{key:'Phase 0',name:'案件解析',status:'pending'},{key:'Phase 1',name:'OCR分类+提取',status:'pending'},{key:'Phase 2',name:'结构化提取',status:'pending'},{key:'Phase 3',name:'匹配',status:'pending'},{key:'Phase 4',name:'档案整理',status:'pending'},{key:'Phase 5',name:'规则审核',status:'pending'},{key:'Phase 6',name:'计算',status:'pending'},{key:'Phase 7',name:'责任聚合',status:'pending'}])
const ruleLayers = {1:[{code:'1.1',name:'身份校验',result:'pending'},{code:'1.2',name:'保险期间',result:'pending'},{code:'2.1',name:'材料完整性',result:'pending'}],2:[{code:'1.3.1',name:'特药匹配',result:'pending'},{code:'1.4',name:'医院资质',result:'pending'},{code:'3.1',name:'既往症判断',result:'pending'}],4:[{code:'3.2',name:'赔付计算',result:'pending'}]}
const layerNames = {1:'前置校验',2:'内容审核',3:'特殊规则',4:'计算'}
function statusLabel(s) { return {pass:'通过',reject:'拒赔',supplement:'补材',transferToManual:'转人工',pending:'待执行',running:'执行中'}[s]||s }
const { events: wsEvents } = useWebSocket(route.params.id)
async function load() { try { c.value = await api.getCase(route.params.id); activePolicy.value = c.value.policy_links?.[0]?.id } catch {} }
async function runAudit() { await api.auditCase(c.value.id); c.value.status = 'running'; phases.value.forEach(p=>{if(p.status==='pending')p.status='running'}) }
async function cancel() { if(confirm('撤销?')){ await api.cancelCase(c.value.id); c.value.status='cancelled' } }
async function doIntervene(action) { await api.intervene(c.value.id,{opinion:interveneText.value,action}); interventions.value.push({time:new Date().toLocaleString(),operator:'当前用户',opinion:interveneText.value,action}); interveneText.value=''; showIntervene.value=false }
onMounted(load)
</script>
<style scoped>
.detail{max-width:1100px;margin:0 auto;padding:24px 24px 80px}
.header{margin-bottom:20px}.header h2{font-size:20px;margin-bottom:8px}
.meta{font-size:13px;color:#666;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.policies{display:flex;gap:8px;margin-top:12px;align-items:center;font-size:13px}
.policies button{padding:4px 12px;border:1px solid #d9d9d9;border-radius:14px;background:#fff;cursor:pointer;font-size:12px}.policies button.active{background:#e6f7ff;border-color:#1a73e8;color:#1a73e8}
.body{background:#fff;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.08)}
.tabs{display:flex;border-bottom:1px solid #e8e8e8;padding:0 16px}.tabs button{padding:12px 20px;border:none;background:none;cursor:pointer;font-size:14px;border-bottom:2px solid transparent}.tabs button.active{border-bottom-color:#1a73e8;color:#1a73e8}
.content{padding:20px;min-height:350px}
.timeline .phase{display:flex;align-items:flex-start;gap:12px;padding:10px 0;border-bottom:1px solid #f0f0f0}.phase .info{flex:1}.phase .info strong{font-size:14px}.phase .detail{font-size:12px;color:#999;margin-top:4px}.phase .time{font-size:12px;color:#999}
.dot{width:12px;height:12px;border-radius:50%;display:inline-block;margin-top:3px;flex-shrink:0}.dot.done{background:#52c41a}.dot.running{background:#1890ff;animation:pulse 1.5s infinite}.dot.pending{background:#d9d9d9}.dot.pass{background:#52c41a}.dot.reject{background:#ff4d4f}.dot.supplement{background:#faad14}@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.events{background:#1e1e1e;color:#d4d4d4;padding:12px;border-radius:6px;margin-top:16px;font-family:monospace;font-size:12px;max-height:200px;overflow-y:auto}.events h4{color:#fff;margin-bottom:8px}
.matrix .layer{margin-bottom:20px}.matrix h4{font-size:13px;color:#666;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid #f0f0f0}
.rule{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #fafafa;font-size:13px}.rule .code{font-family:monospace;color:#1a73e8;font-size:12px}.rule .name{font-weight:500}.rule .result{font-size:11px;padding:2px 8px;border-radius:10px}.result.pass{background:#f6ffed;color:#52c41a}.result.reject{background:#fff2f0;color:#ff4d4f}.result.pending{background:#f0f0f0;color:#999}.rule .reason{color:#999;font-size:12px;flex:1}.lnk{font-size:11px;color:#1a73e8;cursor:pointer;background:none;border:none}
.report .section{margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #f0f0f0}.report h3{font-size:15px;margin-bottom:6px}.report p,.report li{font-size:13px;color:#666}.decision{font-size:20px;font-weight:700}.decision.pass{color:#52c41a}.decision.reject{color:#ff4d4f}
.actions{position:fixed;bottom:0;left:0;right:0;background:#fff;padding:14px 24px;border-top:1px solid #e8e8e8;display:flex;gap:12px;align-items:center;z-index:50}
.btn{padding:8px 20px;border:1px solid #d9d9d9;border-radius:4px;background:#fff;cursor:pointer;font-size:13px}.btn.primary{background:#1a73e8;color:#fff;border:none}
.tag{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px}.tag-pending{background:#f0f0f0;color:#666}.tag-running{background:#e6f7ff;color:#1890ff}.tag-completed{background:#f6ffed;color:#52c41a}
.drawer-overlay{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.3);z-index:100;display:flex;justify-content:flex-end}
.drawer{width:420px;background:#fff;height:100%;padding:24px;overflow-y:auto;box-shadow:-4px 0 12px rgba(0,0,0,.1)}.drawer h3{margin-bottom:16px}.drawer textarea{width:100%;padding:10px;border:1px solid #d9d9d9;border-radius:4px;margin:16px 0;resize:vertical}.btns{display:flex;gap:8px}
</style>
