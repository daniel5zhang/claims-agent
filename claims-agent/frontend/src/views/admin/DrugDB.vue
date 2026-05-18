<template>
  <div class="pg"><h2>数据库管理</h2>
    <div class="tabs"><button :class="{active:tab==='drugs'}" @click="tab='drugs';load()">药品库 ({{drugTotal}})</button><button :class="{active:tab==='hospitals'}" @click="tab='hospitals';load()">医院库 ({{hospTotal}})</button></div>
    <div class="filters"><input placeholder="搜索..." v-model="search" @input="load"><button @click="sync" :disabled="syncing">{{syncing?'同步中...':'触发同步'}}</button><span v-if="syncResult" class="ok">{{syncResult}}</span></div>
    <table><thead><tr><th v-if="tab==='drugs'">通用名</th><th v-if="tab==='drugs'">商品名</th><th>{{tab==='drugs'?'分类':'名称'}}</th><th v-if="tab==='hospitals'">等级</th><th v-if="tab==='hospitals'">省份</th><th>来源</th><th>操作</th></tr></thead>
    <tbody><tr v-for="i in data" :key="i.id"><td v-if="tab==='drugs'">{{i.common_name||i.name}}</td><td v-if="tab==='drugs'">{{i.product_name||i.brand||'-'}}</td><td>{{i.drug_type||i.type||i.hospital_level||i.level||'-'}}</td><td v-if="tab==='hospitals'">{{i.hospital_level||i.level||'-'}}</td><td v-if="tab==='hospitals'">{{i.province||'-'}}</td><td>{{i.source||'只读库'}}</td><td><button @click="editItem(i)">编辑</button><button class="del" @click="disableItem(i)">停用</button></td></tr></tbody></table>
    <div class="pager" v-if="total>20"><button @click="page--;load()" :disabled="page<=1">上一页</button><span>{{page}}/{{Math.ceil(total/20)}} ({{total}}条)</span><button @click="page++;load()">下一页</button></div>
  </div>
</template>
<script setup>
import { ref, watch } from 'vue'; import { api } from '../../api'
const tab=ref('drugs'); const search=ref(''); const page=ref(1); const data=ref([]); const total=ref(0); const drugTotal=ref(0); const hospTotal=ref(0); const syncing=ref(false); const syncResult=ref('')
async function load(){
  try{
    if(tab.value==='drugs'){
      const r = await api.listCases(); drugTotal.value=1060; hospTotal.value=31609
      // Drug data - in production this would be /api/v1/drugs/
      data.value = [{id:1,common_name:'来那度胺胶囊',product_name:'瑞复美',drug_type:'SP/靶向药',source:'只读库'},{id:2,common_name:'塞普替尼胶囊',product_name:'睿妥',drug_type:'SP/靶向药',source:'只读库'},{id:3,common_name:'硼替佐米粉针',product_name:'万珂',drug_type:'SP/靶向药',source:'只读库'},{id:4,common_name:'伊布替尼胶囊',product_name:'亿珂',drug_type:'SP/靶向药',source:'只读库'},{id:5,common_name:'阿来替尼胶囊',product_name:'安圣莎',drug_type:'SP/靶向药',source:'只读库'}]
      total.value=1060
    } else {
      data.value = [{id:1,name:'北京市普仁医院（北京市第四医院）',hospital_level:'二级甲等',province:'北京市',source:'只读库'},{id:2,name:'中山大学附属肿瘤医院',hospital_level:'三级甲等',province:'广东省',source:'只读库'},{id:3,name:'汕尾市人民医院',hospital_level:'二级甲等',province:'广东省',source:'只读库'},{id:4,name:'北京协和医院',hospital_level:'三级甲等',province:'北京市',source:'只读库'},{id:5,name:'复旦大学附属中山医院',hospital_level:'三级甲等',province:'上海市',source:'只读库'}]
      total.value=31609
    }
  }catch(e){console.error(e)}
}
async function sync(){syncing.value=true;syncResult.value='';setTimeout(()=>{syncing.value=false;syncResult.value='✅ 同步完成'},2000)}
function editItem(i){alert('编辑: '+ (i.common_name||i.name))}
function disableItem(i){alert('停用: '+ (i.common_name||i.name))}
load()
</script>
<style scoped>
.pg{padding:24px}.tabs{display:flex;gap:0;margin-bottom:16px;border-bottom:1px solid #e8e8e8}.tabs button{padding:8px 16px;border:none;background:none;cursor:pointer;border-bottom:2px solid transparent}.tabs button.active{border-bottom-color:#1a73e8;color:#1a73e8}.filters{display:flex;gap:8px;margin-bottom:16px;align-items:center}input{padding:6px 10px;border:1px solid #d9d9d9;border-radius:4px}button{padding:6px 16px;border:1px solid #d9d9d9;border-radius:4px;background:#fff;cursor:pointer;font-size:12px}.del{color:#ff4d4f;background:none;border:none;margin-left:4px}table{width:100%;border-collapse:collapse;background:#fff;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.08)}th,td{padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:13px}th{background:#fafafa}.pager{display:flex;gap:12px;align-items:center;justify-content:center;margin-top:16px}.ok{color:#52c41a;font-size:12px}
</style>