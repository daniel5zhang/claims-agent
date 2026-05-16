# 调研发现 + 设计细节

## 数据库连接

- **Host**: 192.168.0.48:8000 / DB: hmb / Schema: `claim-special-medicine-core`
- **连接方式**: PostgreSQL MCP Server（`.mcp.json`）
- Bash 沙箱网络限制，MCP Server 通过本地 stdio 进程绕过

---

## 深度调研新发现（第三轮）

### 重大发现A：完整 Prompt 模板（从源码提取）

**加载优先级**：`if_prompt_config` 表（项目级）→ `sys_constant`（全局）→ 代码硬编码默认值

#### A1. 适应症审核 Prompt（QianWenUtil，interfaceCode=ai_audit）

```
你将作为理赔案件审核专家，负责对保险理赔案件进行初审审核。你的任务是根据适应症审核要点，
和提供的案件材料，对照审核要点和案件材料，进行审核，得出审核结论。

<适应症审核要点>
{{audit_point}}
</适应症审核要点>

以下是案件材料：
<案件材料>
{{medical_and_disease_info}}
</案件材料>

# 审核规则
1、准确性：所有判定信息来源必须从<案件材料>中获取，严格按照<适应症审核要点>判定，
   不允许发散，不要做推断，不要做默认，缺少证据则结果不通过。
2、信息提取和整理能力：从案件材料中快速提取与审核要点关联的关键信息并匹配。
3、年龄判断：有生日取生日计算，没有生日取证件号第7位年月日判断。
4、治疗线数名词释义：
   - 一线治疗：确诊时间当天或之后首次使用该药品
   - 二线治疗：一线治疗后疾病进展，更换抗癌机理不同的方案
   - 三线治疗：二线治疗后再次换用的方案

输出格式：
{"rule_list": [
  {"ruleId": "1000001", "rule": "非小细胞肺癌，局部晚期或转移性", "result": "0/1", "reason": "..."},
  {"ruleId": "1000002", "rule": "EGFR19号外显子缺失突变", "result": "0/1", "reason": "..."},
  {"ruleId": "1000003", "rule": "一线治疗", "result": "0/1", "reason": "..."},
  {"ruleId": "1000004", "rule": "成人", "result": "1", "reason": "患者年龄44岁，满足该要点。"}
]}
```

#### A2. 档案整理 Prompt（QianWenArchiveUtil，interfaceCode=file_archive）

10条整理规则，核心要点：
1. 按时间顺序排序，标记首次确诊时间、检查时间、住院时间、用药时间
2. 整理确诊时间、确认疾病、疾病分型、详细疾病说明
3. 用药信息：通用名、商品名、用药时间周期，从第一次用药起算第一周期
4. 检查检验：全量整理指标值，明确阳性/阴性结论，不能遗漏
5. 治疗线数分析：严格按材料中明确的日期判断，不允许推断
6. 输出结构：患者身份信息 → 确诊信息 → 治疗路径 → 既往诊疗 → 本次就诊 → 用药信息 → 手术+检验

#### A3. 药品提取 Prompt（QianWenGetDrugUtil，interfaceCode=get_drugs）

```
#你是一名数据分析和提取专家
1、请从<picData>中提取药品名称
2、如提取到多个药品则用逗号隔开并去掉重复药品
提取的内容: <picData>{{picData}}</picData>
#输出要求: 仅输出提取的药品名称，如未识别到药品则返回null
```

### 重大发现B：适应症审核要点体系（完整）

**数据来源**：`if_product_drug_list_option` 表的 `REVIEW_POINT` 字段（非 if_drug_audit_points）

**审核要点类型**（5大类）：

| 类型 | 示例要点 |
|------|---------|
| 疾病诊断 | 非小细胞肺癌，局部晚期或转移性 |
| 基因突变 | EGFR19号外显子缺失突变或21号外显子L858置换突变 |
| 治疗线数 | 一线治疗 / 二线治疗 / 三线治疗 |
| 患者特征 | 成人 / 儿童 / 年龄≥18岁 |
| 用法用量 | 剂量符合说明书推荐范围 |

**审核要点输出格式**：每个要点独立判断，result=1通过/0不通过，附具体原因

**数据流**：
```
if_product_drug_list_option.REVIEW_POINT（要点定义）
  → 审核时传入 QianWenUtil prompt 的 {{audit_point}}
  → LLM 返回 rule_list（每个要点的判断结果）
  → 保存到 if_attachment_audit_point_detail（每个要点一条记录）
  → 人工复核更新 manual_review / not_pass_type
```

### 重大发现C：if_attachment_audit_detail 有 333,610 条记录但关键字段全空

说明：适应症审核要点数据存储在 `if_attachment_audit_point_detail` 表（通过 attachment_audit_detail_id 关联），不在 detail 表本身。detail 表只存储整体审核结论，point_detail 表存储每个要点的细粒度结果。

### 重大发现D：if_drug_diseases 适应症数据样本

| 药品 | 适应症大类 | 适应症小类 | 适应症说明 |
|------|---------|---------|---------|
| 醋酸阿比特龙（泽珂） | 前列腺癌 | 转移性去势抵抗性前列腺癌 | 与泼尼松合用，治疗mCRPC |
| 注射用硼替佐米（万珂） | 淋巴瘤 | 套细胞淋巴瘤 | 复发或难治性，至少接受过一种治疗 |
| 硫酸拉罗替尼（维泰凯） | 实体瘤 | NTRK融合的实体瘤 | 携带NTRK融合基因，局部晚期或转移性 |
| 甲磺酸仑伐替尼（倍美妥） | 肝癌 | 肝细胞癌 | 既往未接受过全身系统治疗的不可切除肝细胞癌 |

---



### 重大发现0：开启智能审核的项目（17个，全为惠民保类型）

| 项目代码 | 项目名称 | 险种 | audit_point_mark | simple_audit |
|---------|---------|------|-----------------|-------------|
| AHHMB2026 | 安徽惠民保2026 | TY | ✅ | — |
| BJ2025/BJ2026 | 北京普惠健康保 | TY,YL,QY | ✅/❌ | — |
| XHYLB202501/02/601/602 | 西湖益联保系列 | TY,YL | ✅ | — |
| LJHMB2025/2026 | 龙江惠民保 | TY | ✅ | 0（关闭简单审核）|
| ZGJTFABZK2024/2025系列 | 职工家庭防癌抗癌保障卡 | TY,YL,QY | ✅ | — |
| RBC-HMB202501/02 | 惠蒙保2025 | TY,YL | ❌ | 1（简单审核）|

**关键配置字段含义**：
- `smart_audit=1`：开启完整智能审核（19条规则全跑）
- `ty_ai_process=Y`：仅开启特药自动审（简化流程）
- `audit_point_mark=1`：启用适应症审核要点标记（药品要点审核）
- `simple_audit=1`：简单审核模式（只判断是否提取到药单内药品）
- `risk_type`：险种范围（TY=特药, YL=医疗, QY=其他）

---

### 重大发现1：规则体系三个维度（完整版）

**维度一：通用规则（所有项目共用，2条）**
| 规则 | 逻辑 | 触发条件 |
|------|------|---------|
| 用药校验 | 提取到药单内→通过；未提取→待补材；不在药单→不通过 | 所有案件 |
| 保障时间校验 | 按发票类型（药房/门诊/住院/无发票）4种逻辑 | 所有案件 |

**维度二：险种责任规则（按项目配置，16条+矩阵）**
编号体系：1.x身份保障 → 2.x材料审核 → 3.x既往症计算 → 4.x特殊案件 → 矩阵汇总

**维度三：药品适应症审核要点规则（按药品+适应症配置）**
- 每个药品（drug_id）× 每个适应症（drug_diseases_id）有独立的审核要点
- 审核要点存储在 `if_drug_audit_points` 表（drug_diseases_id → audit_point）
- 执行结果存储在 `if_attachment_audit_point_detail`（每个要点独立判断）
- 人工复核结果存储在 `if_case_drug_point`（最终结论）
- 支持多版本重审（version字段）

**三维度关联关系**：
```
项目（if_project_details）
  └── 险种责任（if_insurance）
        └── 规则配置（if_project_smart_audit_config）
              ├── smart_audit=1 → 执行维度一+维度二（19条规则）
              ├── audit_point_mark=1 → 额外执行维度三（适应症要点）
              └── simple_audit=1 → 仅执行简化版用药校验
```

---

`ai_model_call_log` 中实际有 **17个 task_description**，加上通用规则共 **19条**：

**通用审核规则（跨项目）**
| 规则 | 逻辑 |
|------|------|
| 用药校验 | 提取到药单内药品→通过；未提取→待补材；提取到但不在药单内→不通过 |
| 保障时间校验 | 按发票类型分4种逻辑（药房/门诊/住院/无发票） |

**蒙惠保独立规则（编号体系）**
| 编号 | 规则名 | 核心逻辑 |
|------|--------|---------|
| 1.1 | 身份校验 | 医保归属地必须在内蒙古12个统筹区内 |
| 1.2 | 保险期间冲突检测 | 住院/门诊/药店发票各有不同日期校验逻辑 |
| 1.3.1 | 特药匹配-通用名 | CaseExtend.aiAuditResult="1"→pass，否则reject |
| 1.3.2 | 特殊疾病白名单 | 保单免责疾病列表 × 档案疾病类型匹配 |
| 1.4 | 医院资质 | 联网搜索，等级≥二级且为公立普通部或医保定点 |
| 2.1 | 材料缺失判定 | 按就诊场景（院内住院/院内门诊/院外购药）判定所需材料 |
| 2.2.1 | 身份证有效性 | 至少一正一反；有效期覆盖报案日期 |
| 2.2.2 | 处方有效性 | 日期差≤7天；用量≤周期；签章；信息匹配；购药人姓名；数量一致 |
| 2.2.3 | 医保结算单 | 有效期内；金额与发票一致 |
| 2.2.4 | 住院费用清单 | 与住院病历住院天数、费用明细一致 |
| 3.1 | 既往症时间筛除+疾病过滤 | 四层判定（见下方详细说明） |
| 3.2 | 赔付金额计算 | MAX(0, 总费用-实际补偿-其他补偿) |
| 4.1 | 未成年人 | <18岁触发；监护人为父母→pass；非父母需法院证明 |
| 4.2 | 身故案件 | 识别身故信息；需死亡三证+继承人材料 |
| — | **汇总结果矩阵** | 聚合所有规则结果，生成最终审核矩阵报告 |

### 重大发现2：既往症判断是4层模型（非3层）

从生产 prompt 提取的完整逻辑：
```
层1：确诊日期 >= 保单起期 → 非既往症（pass）
层2：确诊日期 < 保单起期 且 疾病不在特定既往病症范围内 → 非既往症（pass）
层3：确诊日期 < 保单起期 且 疾病在特定既往病症范围内 → 既往症（reject）
（层4：既往症关联性分析 — 对层3结果做进一步关联分析）
```

**特定既往病症范围**（触发既往症的疾病类型）：
- 肿瘤：恶性肿瘤（含白血病、淋巴瘤）
- 肝肾疾病：肾功能不全；肝硬化、肝功能不全
- 心脑血管及糖脂代谢：缺血性心脏病、慢性心功能不全（Ⅲ级及以上）、脑血管疾病、Ⅲ级高血压、糖尿病伴并发症
- 肺部疾病：慢性阻塞性肺病、慢性呼吸衰竭

### 重大发现3：归档内容结构（6大板块）

从 `if_case_archive.archive_content` 实际数据提取的完整结构：
```
<治疗路径材料>
1. 确诊信息
   - 确诊时间（首次病理报告确诊时间）
   - 确认疾病（出院诊断/病理报告）
   - 疾病分型
   - 详细疾病说明及进程

2. 治疗路径
   - 住院/门诊就诊时间列表

3. 既往诊疗情况分析
   - 疾病首次确诊时间
   - 既往就诊时间
   - 既往检查检验信息（内容/方式/阳性指标/时间）
   - 既往诊治经过
   - 药物治疗方案
   - 手术治疗情况
   - 既往治疗效果

4. 本次就诊的诊疗情况
   - 就诊医院
   - 出院诊断
   - 疾病首次确诊时间
   - 药物治疗方案（单药/联合）
   - 治疗线数
   - 用药依据

5. 用药信息（处方笺）
   - 处方开具日期/医院/药品名称/规格/数量/用法用量/通用名/商品名/用药时间

6. 手术治疗情况 + 检查检验信息
</治疗路径材料>
```

### 重大发现4：适应症审核有独立的审核要点体系

`if_attachment_audit_detail` 表结构揭示适应症审核的完整数据模型：
- `audit_point`：审核要点（如"适应症符合性"）
- `audit_point_detail`：审核要点详细描述
- `point_result`：审核要点结果
- `analyse_result`：大模型分析结果（JSON）
- `indication`：适应症
- `cover_diseases_detail`：适应症小类
- `version`：重审历史版本（支持多次重审）
- `modify_desc`：重审原因

### 重大发现5：案件审核结论编码体系

`if_case_audit` 表的编码：
- `audit_type`：CS（初审）/ FS（复审）/ LSFS（理算复审）
- `audit_conclusion`：PS（通过）/ NP（不通过）/ ZCPF（正常赔付）/ JP（拒赔）
- `not_pass_type`：YPJL（药品记录）等
- `rejected_type`：拒赔类型编码

### 重大发现6：if_diagnostic_info 是核心处方药品表

字段涵盖完整的处方信息：
- 药品基础：drug_name, common_name, specification, price, unit, amount
- 处方信息：prescription_type, prescription_no, prescription_date, prescription_hospitalname, prescription_doctor
- 用药信息：medication_time, dosage, medication_cycle, drug_usage, drug_usage_desc
- 医保信息：is_health_insurance, insurance_type, is_overseas_medicine, is_rare_drug
- 审核结果：audit_opinion, audit_conclusion, auditor, type_of_audit_opinion
- 关联：drug_id, drug_diseases_id, drug_spec_id, insurance_id

### 重大发现7：if_visit_records 是患者随访记录表

记录患者用药后的随访情况：
- visit_type, visit_time, next_visit_time, visit_content
- next_medicine_time（下次用药时间）
- medication_times（用药次数）
- is_charity_apply（是否申请慈善赠药）
- grant_status, grant_quantity, grant_total_amount（赠药信息）

---

## 只读库关键数据摘要

### 生产模型分工
| 任务 | 模型 |
|------|------|
| 信息提取、审核规则 | `qwen3-max` |
| 疾病/医院匹配（高频） | `qwen-plus` / `qwen-plus-latest` |
| OCR 影像件识别 | `qwen-vl-max-latest` |

### 16 条审核规则（优先级顺序）
**层1 — 前置校验（任一失败终止流程）**
| 规则 | 调用量 |
|------|--------|
| 材料缺失判定 | 280 |
| 身份证有效性校验 | 280 |
| 被保险人身份校验 | 283 |
| 保险期间冲突检测 | 273 |

**层2 — 内容审核（可并行）**
| 规则 | 调用量 |
|------|--------|
| 处方有效性校验 | 280 |
| 医保结算单有效性校验 | 175 |
| 住院费用清单有效性校验 | 128 |
| 就诊医院资质联网搜索校验 | 283 |
| 既往症时间筛除+疾病类型过滤 | 94 |
| 既往症判断 | 98 |
| 既往症关联性分析 | 32 |
| 文本提取（药品-材料映射） | 75 |

**层3 — 特殊规则**
| 规则 | 调用量 |
|------|--------|
| 身故案件特殊规则 | 281 |
| 特殊疾病白名单 | 155 |（源码中无，后加）
| 未成年人特殊规则 | 15 |

**层4 — 计算**
| 规则 | 调用量 |
|------|--------|
| 赔付金额计算 | 262 |

### 审核规则统一 Prompt 格式
```
你是一个特药理赔智能审核专家，请根据以下规则和数据进行判断：

规则名称：{rule_name}
规则描述：{rule_description}

审核数据：
{structured_data}

仅提取审核数据中的有效数据进行判断，忽略位置、图像质量、识别置信度等与业务无关的数据

返回结果的字段释义：pass->通过 reject->拒赔 supplement->待补材 transferToManual->转人工。
输出格式：{"result":"pass"/"reject"/"supplement"/"transferToManual","reason":"具体原因"}
```

### 理算算法示例
```
tdyp_001:  Min(药品1单价×数量×赔付比例 + 药品2单价×数量×赔付比例..., 剩余保额)
jin26001:  (账单金额 - 统筹支付 - 自费金额 - 第三方支付 - 大病支付 - 免赔额余额 - 乙类自付) × 赔付比例
ybnyl004:  (发生金额合计 - 社保支付 - 自费金额 - 大病支付 - 第三方支付 - 其他支付 - 自付金额 - 免赔额余额) × 赔付比例
```

### 核心业务表数据量
| 表 | 数据量 | 关键字段 |
|----|--------|---------|
| `if_case` | 706,000+ | case_id, claim_status, insured_id, project_id |
| `if_drug_info` | 1,062 | common_name, product_name, drug_type, drug_category |
| `if_drug_diseases` | 1,000+ | drug_id, cover_diseases, specification_indication |
| `sys_hospital` | 31,603 | code, name, hospital_level, hospital_nature |
| `if_diseases_database` | 大量 | disease_name, disease_code(ICD-10), disease_type |
| `if_insurance` | 100+ | insurance_code, insurance_liability, duty_type, ratios |
| `if_duty_algorithm` | 20+ | algorithm_id, algorithm_logic |
| `ai_model_call_log` | 27,157 | task_code, request_content, response_content |
| `sys_constant` | 9条核心 | AiOCRPrompt, AiArchivePrompt, AiAuditContent, AiFormatJsonContent, AiOCRModel, AiAuditModel, AiArchiveModel, AiOCRSpareModel, OpenAi |

---

## 新 Agent 数据库 Schema 设计

```sql
-- 项目库
CREATE TABLE projects (
  id VARCHAR PRIMARY KEY,
  project_code VARCHAR UNIQUE NOT NULL,
  project_name VARCHAR NOT NULL,
  product_name VARCHAR,
  company_name VARCHAR,
  project_type VARCHAR,        -- 特药/医疗/意外等
  claim_type VARCHAR,
  start_date DATE,
  end_date DATE,
  status VARCHAR DEFAULT 'ACTIVE'
);

-- 产品/责任库
CREATE TABLE insurance_products (
  id VARCHAR PRIMARY KEY,
  insurance_code VARCHAR UNIQUE NOT NULL,
  insurance_liability VARCHAR NOT NULL,
  duty_type VARCHAR,           -- ty=特药, yl=医疗, hlqy=护理
  security_lines DECIMAL,      -- 保额（万元）
  deductible_excess INTEGER,   -- 免赔额
  waiting_period INTEGER,      -- 等待期（天）
  health_claims DECIMAL,       -- 赔付比例%
  pre_existing_disease_ratio DECIMAL,
  not_pre_existing_disease_ratio DECIMAL,
  algorithm_id VARCHAR
);

-- 理算算法库
CREATE TABLE calculation_algorithms (
  id VARCHAR PRIMARY KEY,
  algorithm_id VARCHAR UNIQUE NOT NULL,
  algorithm_logic TEXT NOT NULL,
  algorithm_describe VARCHAR
);

-- 药品库
CREATE TABLE drugs (
  id VARCHAR PRIMARY KEY,
  common_name VARCHAR NOT NULL,
  product_name VARCHAR,
  drug_type VARCHAR,           -- 靶向药/化疗药/罕见病药等
  drug_category VARCHAR,       -- SP=特药, NORM=普通
  is_original VARCHAR,
  is_first_drug VARCHAR,
  is_overseas_medicine VARCHAR,
  target VARCHAR,              -- 靶点
  listed_status VARCHAR
);

-- 药品适应症库
CREATE TABLE drug_indications (
  id VARCHAR PRIMARY KEY,
  drug_id VARCHAR REFERENCES drugs(id),
  cover_diseases VARCHAR,
  cover_diseases_detail VARCHAR,
  specification_indication TEXT,
  month_drug_cost VARCHAR,
  is_charity VARCHAR
);

-- 医院库
CREATE TABLE hospitals (
  id VARCHAR PRIMARY KEY,
  code VARCHAR UNIQUE,
  name VARCHAR NOT NULL,
  hospital_level VARCHAR,      -- 三级甲等/二级乙等等
  hospital_nature VARCHAR,     -- 公立/私立/股份
  specialty_nature VARCHAR,
  province VARCHAR,
  city VARCHAR,
  district VARCHAR
);

-- 疾病库（ICD-10）
CREATE TABLE diseases (
  id VARCHAR PRIMARY KEY,
  disease_name VARCHAR NOT NULL,
  disease_code VARCHAR,        -- ICD-10编码
  disease_type VARCHAR
);

-- 审核规则库
CREATE TABLE audit_rules (
  id VARCHAR PRIMARY KEY,
  rule_name VARCHAR UNIQUE NOT NULL,
  rule_description TEXT,
  prompt_template TEXT NOT NULL,
  layer INTEGER,               -- 1=前置, 2=内容, 3=特殊, 4=计算
  priority INTEGER,
  is_blocking BOOLEAN DEFAULT FALSE,
  model VARCHAR DEFAULT 'qwen3-max',
  is_active BOOLEAN DEFAULT TRUE
);

-- 提示词库
CREATE TABLE prompt_templates (
  id VARCHAR PRIMARY KEY,
  code VARCHAR UNIQUE NOT NULL,
  content TEXT NOT NULL,
  description VARCHAR,
  model VARCHAR,
  version INTEGER DEFAULT 1,
  updated_at TIMESTAMP
);

-- 案件记录（Agent新建）
CREATE TABLE claim_cases (
  id VARCHAR PRIMARY KEY,
  case_no VARCHAR UNIQUE NOT NULL,
  project_id VARCHAR REFERENCES projects(id),
  insured_name VARCHAR,
  insured_id_no VARCHAR,
  report_date TIMESTAMP,
  status VARCHAR,              -- processing/completed/manual/rejected
  final_result VARCHAR,        -- pass/reject/supplement/transferToManual
  compensation_amount DECIMAL,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 审核日志
CREATE TABLE audit_logs (
  id VARCHAR PRIMARY KEY,
  case_id VARCHAR REFERENCES claim_cases(id),
  phase VARCHAR,               -- ocr/extraction/matching/audit/calculation/archive
  tool_name VARCHAR,
  rule_name VARCHAR,
  model VARCHAR,
  request_content TEXT,
  response_content TEXT,
  result VARCHAR,
  reason TEXT,
  duration_ms INTEGER,
  created_at TIMESTAMP DEFAULT NOW()
);
```

---

## UI 设计线框图

### 页面1：案件列表
```
┌─────────────────────────────────────────────────────────┐
│  理赔 Agent 管理台                          [新建案件]   │
├─────────────────────────────────────────────────────────┤
│  [全部] [待处理] [审核中] [已完成] [转人工]   搜索...   │
├──────┬──────────┬──────┬──────────┬──────────┬─────────┤
│案件号 │ 被保险人 │ 险种 │  报案时间 │  当前状态 │  操作  │
├──────┼──────────┼──────┼──────────┼──────────┼─────────┤
│C0001 │ 张**     │ 特药 │ 05-12 09:│ ████░░ 审│ [查看] │
│C0002 │ 李**     │ 特药 │ 05-11 14:│ ██████ 完│ [查看] │
│C0003 │ 王**     │ 特药 │ 05-11 10:│ ████░░ 转│ [查看] │
└──────┴──────────┴──────┴──────────┴──────────┴─────────┘
```

### 页面2：案件详情（核心页面）
```
┌──────────────────────────────────────────────────────────────────┐
│  案件 C0001 — 张** — 特药险                        [转人工] [关闭]│
├────────────────┬─────────────────────────┬───────────────────────┤
│                │   流程时间轴             │   当前阶段详情        │
│  附件预览      │                          │                       │
│                │  ✅ OCR识别    09:01     │  ┌─ 审核结果 ────┐   │
│  [处方.jpg]    │  ✅ 信息提取   09:02     │  │ ✅ 身份校验 通过│   │
│  [病历.pdf]    │  ✅ 匹配核验   09:03     │  │ ✅ 保单期间 通过│   │
│  [账单.jpg]    │  🔄 规则审核   09:04 ←  │  │ ✅ 处方有效 通过│   │
│                │  ⬜ 金额计算            │  │ 🔄 医院资质 审核│   │
│  ─────────     │  ⬜ 归档输出            │  │ ⬜ 既往症分析   │   │
│                │                          │  └────────────────┘   │
│  提取信息：    │                          │                       │
│  药品：来那度胺│                          │  医院：上海市第一人民 │
│  疾病：多发性骨│                          │  等级：三级甲等 ✅    │
│  医院：上海市第│                          │  性质：公立 ✅        │
│  账单：¥28,000 │                          │  联网核查：通过 ✅    │
│                │                          │                       │
├────────────────┴─────────────────────────┴───────────────────────┤
│  最终决策：[待定]    理算金额：计算中...    [查看完整报告]        │
└──────────────────────────────────────────────────────────────────┘
```

### 页面3：规则管理（Admin）
```
┌─────────────────────────────────────────────────────────┐
│  审核规则管理                              [新增规则]    │
├──────┬──────────────────┬──────┬──────┬────────────────┤
│ 层级 │ 规则名称          │ 模型 │ 状态 │ 操作           │
├──────┼──────────────────┼──────┼──────┼────────────────┤
│  1   │ 材料缺失判定      │ q3mx │ ✅启 │ [编辑] [测试] │
│  1   │ 身份证有效性校验  │ q3mx │ ✅启 │ [编辑] [测试] │
│  2   │ 处方有效性校验    │ q3mx │ ✅启 │ [编辑] [测试] │
│  2   │ 就诊医院资质校验  │ q3mx │ ✅启 │ [编辑] [测试] │
│  3   │ 特殊疾病白名单    │ q3mx │ ✅启 │ [编辑] [测试] │
└──────┴──────────────────┴──────┴──────┴────────────────┘
```

---

## 技术栈选型

| 层 | 技术 | 原因 |
|----|------|------|
| Agent框架 | Anthropic SDK（Python） | 原生tool use，精细控制 |
| 并行执行 | ThreadPoolExecutor | 子agent并行，简单可靠 |
| 数据库 | PostgreSQL | 生产级，支持全文搜索 |
| 向量搜索 | ChromaDB（本地） | 药品适应症语义匹配 |
| Web框架 | FastAPI | 异步，WebSocket支持 |
| 前端 | HTMX + Alpine.js | 轻量，实时更新无需React |
| 实时推送 | WebSocket | 流程状态实时更新 |
| 模型接入 | OpenAI兼容接口 | qwen系列统一接入方式 |

---

## 深度调研新发现（第四轮）— 数据库直接确认

### 重大发现E：sys_constant 完整提示词（从DB直接读取）

**正确 Schema**：`claim-special-medicine-core`（103张表，之前一直在 public schema 查询导致找不到）

| code | 用途 | 模型 |
|------|------|------|
| `AiAuditContent` | 适应症审核 prompt | qwen3-max |
| `AiOCRPrompt` | OCR分类+提取（22大类） | qwen-vl-max-latest |
| `AiArchivePrompt` | 档案整理（10条规则） | qwen3-max |
| `AiFormatJsonContent` | 提取内容转标准JSON | qwen3-max |
| `AiOCRSpareModel` | OCR备用模型列表 | qwen-vl-max,qwen-vl-max-2025-08-13,qwen-vl-max-2025-04-08 |

**AiAuditContent 关键审核规则（6条）**：
1. 准确性：所有判定信息来源必须从案件档案中获取，不允许发散推断
2. 信息提取：快速提取与审核要点关联的关键信息并匹配
3. 年龄判断：有生日取生日计算，没有生日取证件号第7位年月日
4. 无"既往"描述时：依据最近一次治疗和用药情况判定
5. 疾病描述匹配：不要扩展限定（如"单纯/非单纯"），同义不同词要仔细匹配
6. 输出格式：`{"rule_list": [{"ruleId":"...","rule":"...","result":"0/1","reason":"..."}]}`

**AiOCRPrompt 22大分类**（完整）：
- 大类1：自然人客户信息登记表
- 大类2：身份证明资料（身份证正/反面、户口本、社保卡、退役军人证等）
- 大类3：医疗资料（病历、出入院记录、基因检测报告、病理报告、心电图）
- 大类4：医疗费用资料（费用清单、收费票据、发票、结算单）
- 大类7：银行卡
- 大类9：保险单凭证
- 大类17：药品处方
- 大类21：手写体

### 重大发现F：药品适应症数据样本（if_drug_diseases）

| 通用名 | 商品名 | 适应症疾病 |
|--------|--------|-----------|
| Venetoclax | VENCLEXTA | 白血病 |
| Trastuzumab Deruxtecan | Enhertu | 乳腺癌 |
| 阿布昔替尼片 | 希必可 | 特应性皮炎 |
| 依维莫司片 | 飞尼妥 | 胰腺神经内分泌瘤 |
| 甲磺酸伊马替尼片 | 格列卫 | 肥大细胞增生症 |
| 替利珠单抗注射液 | 特瑞可 | 1型糖尿病 |
| 伊匹单抗 | Yervoy | 结直肠癌 |

**if_drug_info 表**：1062条药品记录，`indication` 字段为空（适应症存在 if_drug_diseases 表）
**if_drug 表**：599条（产品维度药品，含 indication 字段但为空，适应症在 if_drug_diseases）

### 重大发现G：if_case_drug_point 表结构（药品审核要点结果）

字段：`case_id`, `product_drug_list_option_id`, `drug_id`, `audit_point_conclusion`, `type_of_audit_np`, `audit_detail`

- `product_drug_list_option_id`：关联到产品药品适应症选项（即审核要点来源）
- `audit_point_conclusion`：审核结论（pass/reject/supplement/transferToManual）
- `type_of_audit_np`：不通过类型
- `audit_detail`：AI审核详情（JSON格式，含每条要点的结果和原因）

---

## 深度调研新发现（第五轮）— if_prompt_config 完整数据

**重大发现**：`if_prompt_config` 表共 **38 条全局配置**（project_id 全为 null），比 sys_constant 丰富得多，揭示了完整的 AI 处理流水线。

### 完整 interface_code 清单

| interface_code | 名称 | 主模型 | 备用模型 |
|---|---|---|---|
| `ocr_type` | 识别图片分类 | qwen3.6-plus | kimi-k2.5, qwen-vl-max |
| `ocr_data` | 识别图片提取内容 | qwen3.6-plus | kimi-k2.5, qwen-vl-max |
| `1` | 申请授权资料类型提取 | qwen3.6-plus | kimi-k2.5 |
| `2` | 身份证明资料提取 | qwen3.6-plus | kimi-k2.5 |
| `3` | 医疗诊治资料提取 | qwen3.6-plus | kimi-k2.5 |
| `4` | 费用类型提取 | qwen3.6-plus | kimi-k2.5 |
| `7` | 银行卡提取 | qwen3.6-plus | kimi-k2.5 |
| `9` | 保险单凭证提取 | qwen3.6-plus | kimi-k2.5 |
| `17` | 处方类型提取 | qwen3.6-plus | kimi-k2.5 |
| `41` | 发票提取 | qwen3.6-plus | kimi-k2.5 |
| `42` | 结算单提取 | qwen3.6-plus | kimi-k2.5 |
| `43` | 费用清单提取 | qwen3.6-plus | kimi-k2.5 |
| `get_medical_bill` | 提取医疗账单 | qwen3.6-plus | qwen3-max-2025-09-23 |
| `get_medical_info` | 提取就诊信息 | qwen3.6-plus | qwen3-max-2025-09-23 |
| `get_prescription_drug` | 提取处方用药信息 | qwen3.6-plus | qwen3-max-2025-09-23 |
| `get_drugs` | 提取药品（标准化） | qwen-plus-latest | qwen-plus |
| `get_drugs`(180) | 匹配药品（知识库） | qwen3.6-plus | kimi-k2.5 |
| `get_compared_drugs` | 药品比对（Y/N） | qwen3-max | qwen-flash |
| `get_hospital` | 匹配机构（×4并行） | qwen-plus | qwen-plus-latest |
| `get_disease` | 匹配疾病（×5并行） | qwen3-max | qwen3-max-2025-09-23 |
| `get_disease_before` | 匹配疾病前置过滤 | qwen3-max | qwen3-max-2025-09-23 |
| `get_compared_detail` | 字段比对 | qwen3-max | qwen3-max-2025-09-23 |
| `get_drugs_point` | 适应症拆解+审核要点提取 | qwen3-max | qwen3-max-2025-09-23 |
| `get_doc_content` | 识别药品清单内容 | qwen3-max | qwen3-max-2025-09-23 |
| `get_on_ins` | 是否在保判断 | qwen3-max | qwen3-max-2025-09-23 |
| `ai_audit` | 智能审核（适应症） | qwen3-max | qwen3-max-2025-09-23 |
| `ai_audit_re` | 智能审核重审 | qwen3-max | qwen3-max-2025-09-23 |
| `file_archive` | 档案归档（文本） | qwen3-max | qwen3-max-2025-09-23 |
| `file_archive_json` | 归档内容整理为JSON | qwen3-max | qwen3-max-2025-09-23 |
| `format_doc_content` | 格式化识别内容 | qwen-flash | qwen-flash-2025-07-28 |

### 新发现的模型体系

| 模型 | 用途 | 特点 |
|------|------|------|
| `qwen3.6-plus` | OCR分类+提取（主力） | 新版，替代 qwen-vl-max |
| `kimi-k2.5` | OCR备用 | 月之暗面，多模态 |
| `qwen-flash` | 格式化/轻量任务 | 快速低成本 |
| `qwen3-max-2025-09-23` | 审核/归档备用 | 最新版 qwen3-max |
| `qwen-plus-latest` | 药品提取/机构匹配 | 中等成本 |

### 关键 Prompt 设计要点

**get_drugs_point（适应症拆解）**：
- 输入：`{{xiangqing}}`（适应症描述详情）
- 输出：JSONArray，每条包含 indication_id, disease_category, disease_subcategory, audit_points
- audit_points 结构：point_1（疾病状态）, point_2（基因检测）, point_3（联合用药）, point_4（治疗线数）, point_5（患者人群）, point_6（治疗阶段）, point_7（既往治疗）
- **这是构建药品适应症审核要点库的核心工具**

**get_prescription_drug（处方提取）**：27个字段，包含：
- 基础：prescription_type/no/doctor/hospitalname/date
- 药品：drug_id, spec_id, drug_name, common_name, specification, unit, dose, amount
- 医保：is_health_insurance, insurance_type, is_overseas_medicine
- 业务：medication_time, medication_cycle, drug_times, estimate_medication_times, prospect_pay_amount, duty

**get_medical_bill（账单提取）**：24个字段，包含：
- 发票：bill_type(1住院/2门诊/3药店), ticket_type(1电子/2增值税/3纸质)
- 金额：invoice_money, social_security_all_amount, social_security_amount, severe_illness_amount, personal_payment, self_pay_amount, tripartite_amount, other_amount
- 明细：drug_name, drug_amount, drug_unit_price, drug_sum, project_type(TSYP/TSYPYBW)

**get_on_ins（在保判断）**：
- 输入：`{{medical_data}}` + `{{ins_date}}`
- 输出：`{"onIns": "1/0", "reason": "..."}`
- 逻辑：保险终止日期 >= 入院/出院时间 >= 保险生效日期

**ocr_type（图片分类）**：
- 优先级：财务凭证 > 医疗执行文书 > 身份证明
- 防混淆：医嘱单(大3) vs 费用清单(大4) vs 发票(大4) vs 处方(大17)
- 输出：`{"bigType": "3", "smallType": "医嘱单"}`

### 完整 AI 处理流水线（修订版）

```
附件上传
  ↓
[ocr_type] 图片分类 → bigType + smallType
  ↓
[ocr_data / 按bigType分发] 内容提取 → 结构化JSON
  ↓
[format_doc_content] JSON格式化校验
  ↓
并行提取：
  ├── [get_medical_bill] 账单提取（发票/结算单/费用清单）
  ├── [get_medical_info] 就诊信息提取（确诊时间/疾病/医院）
  └── [get_prescription_drug] 处方用药提取（27字段）
  ↓
并行匹配：
  ├── [get_drugs × 2] 药品标准化 + 知识库匹配
  ├── [get_compared_drugs] 药品比对（Y/N）
  ├── [get_hospital × 4] 机构匹配（并行4路）
  ├── [get_disease_before + get_disease × 5] 疾病匹配（并行5路）
  └── [get_on_ins] 在保判断
  ↓
[ai_audit] 适应症审核（基于 get_drugs_point 生成的审核要点）
  ↓
[ai_audit_re] 重审（如需要）
  ↓
[file_archive] 档案归档（文本版）
  ↓
[file_archive_json] 归档结构化（JSON版）
```
