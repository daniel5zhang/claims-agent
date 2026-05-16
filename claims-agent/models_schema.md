# Models Schema — 保险理赔 Agent

从 task_plan.md 提取，按 Django app 分组。开发时作为 `models.py` 直接参考。

---

## apps/cases — 案件模块

### Case（案件）
```python
class Case(models.Model):
    case_no = models.CharField(max_length=64, unique=True)       # 系统案件号，主键标识
    source_system = models.CharField(max_length=3)               # OLD / MAN / API
    source_case_no = models.CharField(max_length=64, null=True)  # 原始案件号
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    insured_id = models.CharField(max_length=32)                 # 出险人标识
    insured_name = models.CharField(max_length=64)
    id_number = models.CharField(max_length=18)
    phone = models.CharField(max_length=20)
    diagnosis = models.CharField(max_length=256)
    hospital_name = models.CharField(max_length=256, null=True)  # 报案时填写参考值
    report_date = models.DateTimeField()
    risk_date = models.DateTimeField(null=True)
    claim_mode = models.CharField(                               # direct / reimbursement
        max_length=16, default='reimbursement')
    claim_type = models.CharField(max_length=32, default='SP')   # SP/SR/MED
    status = models.CharField(max_length=32, default='pending')  # pending/running/supplement_required/manual_review/completed/error/cancelled
    priority = models.CharField(                                 # normal / urgent
        max_length=16, default='normal')
    priority_set_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    priority_set_at = models.DateTimeField(null=True)
    max_execution_minutes = models.IntegerField(default=120)
    agent_started_at = models.DateTimeField(null=True)
    cancelled_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='cancelled_cases')
    cancelled_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['insured_id']),
            models.Index(fields=['status']),
            models.Index(fields=['project_id']),
            models.Index(fields=['created_at']),
            models.Index(fields=['case_no']),
        ]
```

### ClaimReport（报案信息）
```python
class ClaimReport(models.Model):
    case = models.OneToOneField(Case, on_delete=models.CASCADE, related_name='report')
    report_person_name = models.CharField(max_length=64)         # 报案人姓名
    insured_relation = models.CharField(max_length=32, null=True)
    report_person_phone = models.CharField(max_length=20)
    report_person_sex = models.CharField(max_length=4, null=True)
    apply_claim_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True)
```

### Attachment（附件）
```python
class Attachment(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='attachments')
    file_name = models.CharField(max_length=256)
    storage_path = models.CharField(max_length=512)              # 本地路径 / 对象存储URL
    attachment_type = models.CharField(max_length=64, null=True)  # OCR识别后可补充
    file_size = models.IntegerField()                            # bytes
    mime_type = models.CharField(max_length=64)
    upload_source = models.CharField(max_length=16, default='local')  # local / oss
    created_at = models.DateTimeField(auto_now_add=True)
```

### PolicyLink（案件关联保单）
```python
class PolicyLink(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='policy_links')
    policy = models.ForeignKey('policies.Policy', on_delete=models.PROTECT)
    source = models.CharField(max_length=16)                     # readonly_db / api / manual_ocr
    created_at = models.DateTimeField(auto_now_add=True)
```

---

## apps/policies — 保单 + 产品 + 限额

### Policy（保单）
```python
class Policy(models.Model):
    policy_no = models.CharField(max_length=64, unique=True)
    product = models.ForeignKey('policies.Product', on_delete=models.PROTECT)
    insured_id = models.CharField(max_length=32)
    coverage_amount = models.DecimalField(max_digits=12, decimal_places=2)
    effective_date = models.DateField()
    expiry_date = models.DateField()
    is_renewal = models.BooleanField(default=False)              # 续保标识
    insurance_order = models.IntegerField(null=True)             # 主次险优先级
    status = models.CharField(max_length=32, default='active')
    source = models.CharField(max_length=32)                     # readonly_db / manual / api
    last_synced_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['insured_id', 'status']),
            models.Index(fields=['policy_no']),
        ]
```

### Product（产品）
```python
class Product(models.Model):
    product_code = models.CharField(max_length=64, unique=True)
    product_name = models.CharField(max_length=256)
    project = models.ForeignKey('policies.Project', on_delete=models.PROTECT)
    claim_type = models.CharField(max_length=32)                 # SP / SR / MED
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Project（项目）
```python
class Project(models.Model):
    project_code = models.CharField(max_length=64, unique=True)
    project_name = models.CharField(max_length=256)
    company_name = models.CharField(max_length=256)
    company_id = models.CharField(max_length=64, null=True)
    project_type = models.CharField(max_length=64)
    claim_type = models.CharField(max_length=32)                 # SP / SR / MED
    start_date = models.DateField(null=True)
    end_date = models.DateField(null=True)
    project_status = models.CharField(max_length=32, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
```

### Liability（险种责任）
```python
class Liability(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='liabilities')
    insurance_code = models.CharField(max_length=64)             # 险种责任编码
    insurance_liability = models.CharField(max_length=256)       # 险种责任名称
    duty_type = models.CharField(max_length=64)                  # 责任类型（特药/住院/门诊/重疾/手术）
    security_lines = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    deductible_excess = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    waiting_period = models.IntegerField(null=True)              # 等待期天数
    pre_existing_disease_ratio = models.DecimalField(max_digits=5, decimal_places=4, null=True)
    not_pre_existing_disease_ratio = models.DecimalField(max_digits=5, decimal_places=4, null=True)
    algorithm_id = models.CharField(max_length=64, null=True)     # 关联算法
    health_claims = models.CharField(max_length=256, null=True)
    renewal_ratio = models.DecimalField(max_digits=5, decimal_places=4, null=True)
    is_active = models.BooleanField(default=True)
```

### InsuranceProduct（产品-责任关系，来自只读库）
```python
class InsuranceProduct(models.Model):
    """从只读库 if_insurance 迁移，Product 的一个版本/变体"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    insurance_code = models.CharField(max_length=64)
    insurance_liability = models.CharField(max_length=256)
    duty_type = models.CharField(max_length=64)
    security_lines = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    deductible_excess = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    waiting_period = models.IntegerField(null=True)
    health_claims = models.CharField(max_length=256, null=True)
    health_claims_outer_ratio = models.DecimalField(max_digits=5, decimal_places=4, null=True)
    pre_existing_disease_ratio = models.DecimalField(max_digits=5, decimal_places=4, null=True)
    not_pre_existing_disease_ratio = models.DecimalField(max_digits=5, decimal_places=4, null=True)
    algorithm_id = models.CharField(max_length=64, null=True)
    status = models.CharField(max_length=16, default='active')
    source_updated_at = models.DateTimeField(null=True)          # 只读库最后更新时间
```

### LimitTracker（限额追踪）
```python
class LimitTracker(models.Model):
    level = models.CharField(                                    # liability / policy / insured / company
        max_length=32, choices=[
            ('liability', '责任层'),
            ('policy', '保单层'),
            ('insured', '出险人层'),
            ('company', '保险公司层'),
        ])
    ref_id = models.CharField(max_length=64)                     # 对应层级的ID
    limit_type = models.CharField(                               # deductible / coverage_annual / coverage_single
        max_length=32, choices=[
            ('deductible', '免赔额'),
            ('coverage_annual', '年度保额'),
            ('coverage_single', '单次限额'),
        ])
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    used_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    source = models.CharField(max_length=32, default='readonly_db')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['ref_id', 'level']),
        ]
```

### LimitHistory（限额变更历史）
```python
class LimitHistory(models.Model):
    tracker = models.ForeignKey(LimitTracker, on_delete=models.CASCADE)
    case = models.ForeignKey('cases.Case', on_delete=models.PROTECT)
    change_amount = models.DecimalField(max_digits=12, decimal_places=2)
    before_amount = models.DecimalField(max_digits=12, decimal_places=2)
    after_amount = models.DecimalField(max_digits=12, decimal_places=2)
    operator = models.CharField(max_length=32)                   # agent / human
    created_at = models.DateTimeField(auto_now_add=True)
```

---

## apps/drugs — 药品库（参考数据）

### Drug（药品）
```python
class Drug(models.Model):
    drug_code = models.CharField(max_length=64, null=True)       # ⚠️ 旧系统多为空
    common_name = models.CharField(max_length=256)
    product_name = models.CharField(max_length=256, null=True)
    production_factory = models.CharField(max_length=256, null=True)
    drug_type = models.CharField(max_length=32, null=True)       # SP / NORM
    drug_category = models.CharField(max_length=64, null=True)
    dosage_form = models.CharField(max_length=64, null=True)
    is_original = models.BooleanField(default=False)
    is_first_drug = models.BooleanField(default=False)
    is_overseas_medicine = models.BooleanField(default=False)
    target = models.CharField(max_length=256, null=True)
    source = models.CharField(max_length=16, default='readonly_db')  # readonly_db / manual
    last_modified_by = models.CharField(max_length=16, default='system')  # system / manual edit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### DrugIndication（药品适应症）
```python
class DrugIndication(models.Model):
    drug = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name='indications')
    disease_name = models.CharField(max_length=256)
    indication_points = models.JSONField(default=list)           # 审核要点列表
    specification_indication = models.TextField(null=True)       # 说明书适应症原文
    month_drug_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    is_charity = models.BooleanField(default=False)
    source = models.CharField(                                   # product_terms / drug_manual
        max_length=32, choices=[
            ('product_terms', '产品条款'),
            ('drug_manual', '药品说明书'),
        ])
    version = models.IntegerField(default=1)
    confirmed_by = models.ForeignKey('organizations.User', null=True, on_delete=models.SET_NULL)
    confirmed_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

---

## apps/hospitals — 医院库（参考数据）

### Hospital（医院）
```python
class Hospital(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=256)
    hospital_level = models.CharField(max_length=32, null=True)
    hospital_level_code = models.CharField(max_length=16, null=True)
    hospital_nature = models.CharField(max_length=64, null=True)
    hospital_nature_code = models.CharField(max_length=16, null=True)
    specialty_nature = models.CharField(max_length=64, null=True)
    province = models.CharField(max_length=64, null=True)
    city = models.CharField(max_length=64, null=True)
    district = models.CharField(max_length=64, null=True)
    source = models.CharField(max_length=16, default='readonly_db')
    last_modified_by = models.CharField(max_length=16, default='system')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

---

## apps/diseases — 疾病库（参考数据）

### Disease（疾病）
```python
class Disease(models.Model):
    # ⚠️ 迁移时注意：只读库列名为 dseases_name, dseases_code（少字母 i）
    disease_name = models.CharField(max_length=256)              # 映射自 dseases_name
    disease_code = models.CharField(max_length=32, null=True)    # 映射自 dseases_code（ICD-10）
    disease_type = models.CharField(max_length=64, null=True)    # 映射自 diseases_type
    created_at = models.DateTimeField(auto_now_add=True)
```

---

## apps/rules — 规则 + 版本管理

### AuditRule（审核规则）
```python
class AuditRule(models.Model):
    rule_code = models.CharField(max_length=64, unique=True)     # 1.1 / 1.3.1 / 3.1 等
    rule_name = models.CharField(max_length=256)
    rule_description = models.TextField(null=True)
    layer = models.IntegerField()                                # 1:前置 2:内容审核 3:特殊规则
    priority = models.IntegerField(default=0)                    # 层内优先级
    is_blocking = models.BooleanField(default=False)             # 失败是否终止
    liability_types = models.JSONField(default=list)             # 触发该规则的险种责任类型
    primary_model = models.CharField(max_length=64, default='qwen3.6-plus')
    result_options = models.CharField(max_length=128, default='pass/reject/supplement/transferToManual')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### RuleVersion（规则版本）
```python
class RuleVersion(models.Model):
    rule = models.ForeignKey(AuditRule, on_delete=models.CASCADE, related_name='versions')
    version = models.CharField(max_length=16)                    # v1.0 / v1.1 / v2.0
    prompt_content = models.TextField()
    primary_model = models.CharField(max_length=64, null=True)
    backup_model = models.CharField(max_length=64, null=True)
    is_current = models.BooleanField(default=False)
    effective_strategy = models.CharField(                       # immediate / next_case / scheduled
        max_length=32, default='immediate')
    effective_date = models.DateTimeField(null=True)
    changed_by = models.ForeignKey('organizations.User', null=True, on_delete=models.SET_NULL)
    change_note = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### MaterialRule（材料完整性规则）
```python
class MaterialRule(models.Model):
    project = models.ForeignKey('policies.Project', on_delete=models.CASCADE)
    liability_type = models.CharField(max_length=64)             # 适用险种责任
    purchase_type = models.CharField(max_length=32)              # outpatient / inpatient / outside_pharmacy
    item_name = models.CharField(max_length=128)                 # 材料名称
    is_required = models.BooleanField(default=True)
    alternatives = models.JSONField(null=True)                   # 替代材料（如处方/医嘱单等价）
    created_at = models.DateTimeField(auto_now_add=True)
```

### ProductTermsDocument（产品条款文档）
```python
class ProductTermsDocument(models.Model):
    product = models.ForeignKey('policies.Product', on_delete=models.CASCADE)
    version = models.CharField(max_length=32)                    # v2024.03
    file_path = models.CharField(max_length=256)
    effective_date = models.DateField()
    is_current = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey('organizations.User', null=True, on_delete=models.SET_NULL)
    notes = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

---

## apps/audit — 审核执行 + 结果

### AuditResult（保单级审核结果）
```python
class AuditResult(models.Model):
    case = models.ForeignKey('cases.Case', on_delete=models.CASCADE)
    policy_link = models.ForeignKey('cases.PolicyLink', on_delete=models.PROTECT)
    status = models.CharField(max_length=32)                     # running / completed / error
    decision = models.CharField(max_length=32, null=True)        # pass / reject / supplement / transferToManual
    pay_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    started_at = models.DateTimeField(null=True)
    completed_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['case_id', 'policy_link_id']),
        ]
```

### RuleResult（单条规则结果）
```python
class RuleResult(models.Model):
    audit_result = models.ForeignKey(AuditResult, on_delete=models.CASCADE, related_name='rule_results')
    rule = models.ForeignKey('rules.AuditRule', on_delete=models.PROTECT)
    rule_version = models.CharField(max_length=16, null=True)
    liability_type = models.CharField(max_length=64, null=True)  # 关联的责任类型
    result = models.CharField(max_length=32)                     # pass / reject / supplement / transferToManual
    reason = models.TextField()                                  # AI 推理原因
    evidence = models.JSONField(null=True)                       # 引用附件 + 坐标
    model_name = models.CharField(max_length=64, null=True)
    duration_ms = models.IntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### RuleEvidence（证据溯源标注）
```python
class RuleEvidence(models.Model):
    rule_result = models.ForeignKey(RuleResult, on_delete=models.CASCADE, related_name='evidences')
    attachment = models.ForeignKey('cases.Attachment', on_delete=models.PROTECT)
    bbox = models.JSONField()                                    # {"x":10,"y":20,"w":100,"h":30,"page":1}
    evidence_type = models.CharField(max_length=32)              # reject_basis / confirm_basis / pending
    label = models.CharField(max_length=256, null=True)          # 标注框说明文字
```

### Intervention（人工介入记录）
```python
class Intervention(models.Model):
    case = models.ForeignKey('cases.Case', on_delete=models.CASCADE, related_name='interventions')
    audit_result = models.ForeignKey(AuditResult, null=True, on_delete=models.SET_NULL)
    phase = models.CharField(max_length=64)                      # archive / audit / calculation
    operator = models.ForeignKey('organizations.User', on_delete=models.PROTECT)
    opinion = models.TextField()                                 # 人工意见
    action = models.CharField(max_length=32)                     # continue / pause / override
    injected_context = models.TextField(null=True)               # 注入 Agent 的上下文
    created_at = models.DateTimeField(auto_now_add=True)
```

### ToolCallRecord（工具调用幂等保护）
```python
class ToolCallRecord(models.Model):
    case = models.ForeignKey('cases.Case', on_delete=models.CASCADE)
    phase_type = models.CharField(max_length=64)
    tool_name = models.CharField(max_length=64)
    call_params_hash = models.CharField(max_length=64)           # 参数哈希，用于去重
    result = models.JSONField()
    status = models.CharField(max_length=16)                     # success / failed
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['case_id', 'tool_name', 'call_params_hash']),
        ]
```

---

## apps/fulfillment — 直赔履约

### FulfillmentOrder（履约单）
```python
class FulfillmentOrder(models.Model):
    case = models.ForeignKey('cases.Case', on_delete=models.PROTECT, related_name='fulfillment_orders')
    drug = models.ForeignKey('drugs.Drug', on_delete=models.PROTECT)
    pharmacy_name = models.CharField(max_length=256, null=True)
    order_status = models.CharField(max_length=32, default='pending')  # pending / confirmed / shipped / delivered / cancelled
    created_at = models.DateTimeField(auto_now_add=True)
```

### PharmacyOrder（药房订单）
```python
class PharmacyOrder(models.Model):
    fulfillment_order = models.OneToOneField(FulfillmentOrder, on_delete=models.CASCADE)
    pharmacy_order_id = models.CharField(max_length=128, null=True)      # 药房系统订单号
    idempotency_key = models.CharField(max_length=256, unique=True)
    status = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)
```

### LogisticsRecord（物流记录）
```python
class LogisticsRecord(models.Model):
    fulfillment_order = models.ForeignKey(FulfillmentOrder, on_delete=models.CASCADE, related_name='logistics')
    tracking_no = models.CharField(max_length=128, null=True)
    status = models.CharField(max_length=32)
    event = models.CharField(max_length=256)
    event_time = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### PharmacySelectionConfig（药房选择规则）
```python
class PharmacySelectionConfig(models.Model):
    project = models.ForeignKey('policies.Project', on_delete=models.CASCADE)
    priority_rules = models.JSONField()
    # [{"field":"is_partner","weight":100}, {"field":"distance_km","weight":-10}, {"field":"stock_score","weight":5}]
    allow_manual_override = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
```

### DirectPaymentAuthConfig（直赔授权有效期）
```python
class DirectPaymentAuthConfig(models.Model):
    project = models.ForeignKey('policies.Project', on_delete=models.CASCADE)
    auth_valid_days = models.IntegerField()                      # 授权有效天数
    warn_before_days = models.IntegerField()                     # 到期前 N 天预警
```

---

## apps/sla — 时效管理

### SLAConfig（时效配置）
```python
class SLAConfig(models.Model):
    project = models.ForeignKey('policies.Project', on_delete=models.CASCADE, null=True)  # null=全局
    product_type = models.CharField(max_length=64, null=True)
    claim_mode = models.CharField(max_length=16, choices=[
        ('direct', '直赔'), ('reimbursement', '事后报销')
    ])
    total_hours = models.IntegerField()                          # 总时效
    warn_before_hours = models.IntegerField()                    # 提前N小时预警
    remind_interval_minutes = models.IntegerField()               # 催办间隔
    escalate_after_hours = models.IntegerField()                  # 超时N小时后升级
    escalate_action = models.CharField(max_length=32)             # notify_supervisor / force_manual
    pause_on_supplement = models.BooleanField(default=True)      # 补材期间暂停计时
```

### SLARecord（时效追踪记录）
```python
class SLARecord(models.Model):
    case = models.OneToOneField('cases.Case', on_delete=models.CASCADE)
    started_at = models.DateTimeField()
    deadline_at = models.DateTimeField()
    paused_at = models.DateTimeField(null=True)
    resumed_at = models.DateTimeField(null=True)
    elapsed_minutes = models.IntegerField(default=0)
    status = models.CharField(max_length=16, default='normal')   # normal / warning / overdue

    class Meta:
        indexes = [
            models.Index(fields=['status', 'deadline_at']),
        ]
```

### SLAEvent（时效事件日志）
```python
class SLAEvent(models.Model):
    sla_record = models.ForeignKey(SLARecord, on_delete=models.CASCADE, related_name='events')
    case = models.ForeignKey('cases.Case', on_delete=models.CASCADE)
    event_type = models.CharField(max_length=32)                 # warning / overdue / escalate / pause / resume
    detail = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### PhaseTimeoutConfig（Phase 超时配置）
```python
class PhaseTimeoutConfig(models.Model):
    phase_type = models.CharField(max_length=64, unique=True)    # ocr_classify / ocr_extract / audit / archive / calculation
    timeout_seconds = models.IntegerField()                      # OCR 建议 300s，审核 600s
    retry_on_timeout = models.BooleanField(default=True)
```

---

## apps/reports — 报告 + 输出文档

### AuditReport（案件全量报告，不可删除）
```python
class AuditReport(models.Model):
    case = models.OneToOneField('cases.Case', on_delete=models.PROTECT)
    phases = models.JSONField()                                  # 每个 Phase 输入/输出
    rule_results = models.JSONField()                            # 每条规则结论+推理
    interventions = models.JSONField()                           # 人工介入记录
    calculation_detail = models.JSONField()                      # 理算过程明细
    final_decision = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)
```

### DocumentTemplate（对外输出文档模板）
```python
class DocumentTemplate(models.Model):
    project = models.ForeignKey('policies.Project', null=True, on_delete=models.SET_NULL)
    product_type = models.CharField(max_length=64, null=True)
    recipient = models.CharField(max_length=32)                  # insured_person / insurer / pharmacy / internal
    doc_type = models.CharField(max_length=64)                   # 理赔决定书 / 审核报告 / 直赔授权单
    template_content = models.TextField()                        # 支持 '{{field_name}}' 变量替换
    output_format = models.CharField(max_length=16)              # pdf / message / api_push
    trigger = models.CharField(max_length=32)                    # auto_on_complete / manual
    is_active = models.BooleanField(default=True)
```

### GeneratedDocument（已生成文档）
```python
class GeneratedDocument(models.Model):
    case = models.ForeignKey('cases.Case', on_delete=models.CASCADE)
    template = models.ForeignKey(DocumentTemplate, on_delete=models.PROTECT)
    content = models.TextField()
    output_file = models.CharField(max_length=256, null=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True)
```

### ReportTemplate（报表模板）
```python
class ReportTemplate(models.Model):
    name = models.CharField(max_length=128)
    report_type = models.CharField(max_length=32)                # monthly / project / reviewer / rule
    output_format = models.CharField(max_length=16, default='excel')
    is_builtin = models.BooleanField(default=False)             # 预置模板不可删除
```

### GeneratedReport（已生成报表）
```python
class GeneratedReport(models.Model):
    template = models.ForeignKey(ReportTemplate, on_delete=models.PROTECT)
    params = models.JSONField()                                  # 生成参数（时间范围/项目）
    file_path = models.CharField(max_length=256)
    generated_by = models.ForeignKey('organizations.User', on_delete=models.PROTECT)
    generated_at = models.DateTimeField(auto_now_add=True)
```

---

## apps/organizations — 组织 + 权限

### Organization（组织）
```python
class Organization(models.Model):
    name = models.CharField(max_length=256)
    parent = models.ForeignKey('self', null=True, on_delete=models.SET_NULL)
    dingtalk_org_id = models.CharField(max_length=64, null=True)
    wecom_corp_id = models.CharField(max_length=64, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Department（部门）
```python
class Department(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='departments')
    name = models.CharField(max_length=256)
    parent = models.ForeignKey('self', null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
```

### User（用户）
```python
class User(models.Model):
    username = models.CharField(max_length=128, unique=True)
    password_hash = models.CharField(max_length=256)
    display_name = models.CharField(max_length=128)
    department = models.ForeignKey(Department, null=True, on_delete=models.SET_NULL)
    dingtalk_id = models.CharField(max_length=64, null=True)
    wecom_id = models.CharField(max_length=64, null=True)
    phone = models.CharField(max_length=20, null=True)
    is_active = models.BooleanField(default=True)
    last_login = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Role（角色）
```python
class Role(models.Model):
    name = models.CharField(max_length=128, unique=True)         # 审核员 / 审核主管 / 规则管理员 / 系统管理员
    permissions = models.JSONField(default=list)                 # 权限列表
    created_at = models.DateTimeField(auto_now_add=True)
```

### ReviewGroup（审核组）
```python
class ReviewGroup(models.Model):
    name = models.CharField(max_length=256)
    members = models.ManyToManyField(User, related_name='review_groups')
    project = models.ForeignKey('policies.Project', null=True, on_delete=models.SET_NULL)
    product_type = models.CharField(max_length=64, null=True)
    pay_amount_min = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    pay_amount_max = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    risk_levels = models.JSONField(null=True)                    # 适用风险等级
    is_default = models.BooleanField(default=False)              # 兜底组
    is_active = models.BooleanField(default=True)
```

### DataAccessPolicy（行级数据访问控制）
```python
class DataAccessPolicy(models.Model):
    subject_type = models.CharField(max_length=32)               # user / group / department
    subject_id = models.CharField(max_length=64)
    scope_type = models.CharField(max_length=32)                 # review_group / project / all
    scope_id = models.CharField(max_length=64, null=True)
    granted_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
```

### DisplayMaskConfig（展示层脱敏配置）
```python
class DisplayMaskConfig(models.Model):
    field_name = models.CharField(max_length=64)                 # id_number / name / phone / diagnosis
    mask_type = models.CharField(max_length=32)                  # full_hide / partial / role_based
    mask_pattern = models.CharField(max_length=64, null=True)    # "310***1234"
    visible_roles = models.JSONField(default=list)               # 哪些角色可见原始值
```

---

## apps/notifications — 通知模块

### NotificationConfig（通知配置）
```python
class NotificationConfig(models.Model):
    project = models.ForeignKey('policies.Project', null=True, on_delete=models.CASCADE)  # null=全局
    product_type = models.CharField(max_length=64, null=True)
    event_type = models.CharField(max_length=64)                 # case_supplement / sla_warning / ...
    roles = models.JSONField()                                   # 接收方角色列表
    channels = models.JSONField()                                # dingtalk / wecom / inapp / api_callback
    template = models.ForeignKey('NotificationTemplate', on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)
```

### NotificationTemplate（通知模板）
```python
class NotificationTemplate(models.Model):
    name = models.CharField(max_length=128)
    channel = models.CharField(max_length=32)                    # dingtalk / wecom / inapp / api_callback
    title_template = models.CharField(max_length=256, null=True)
    body_template = models.TextField()
    is_builtin = models.BooleanField(default=False)
```

### Message（站内消息）
```python
class Message(models.Model):
    recipient = models.ForeignKey('organizations.User', on_delete=models.CASCADE, related_name='messages')
    title = models.CharField(max_length=256)
    body = models.TextField()
    case = models.ForeignKey('cases.Case', null=True, on_delete=models.SET_NULL)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
```

---

## apps/evaluation — 评测 + 模型调用日志

### ModelCallLog（模型调用日志）
```python
class ModelCallLog(models.Model):
    case = models.ForeignKey('cases.Case', null=True, on_delete=models.SET_NULL)
    phase_type = models.CharField(max_length=64)                 # 所属 Phase
    rule_code = models.CharField(max_length=64, null=True)       # 所属规则（审核阶段）
    model_name = models.CharField(max_length=64)
    interface_code = models.CharField(max_length=64)             # task_code 映射后的接口码
    input_tokens = models.IntegerField()
    output_tokens = models.IntegerField()
    cost_yuan = models.DecimalField(max_digits=10, decimal_places=4)
    duration_ms = models.IntegerField()
    is_retry = models.BooleanField(default=False)
    is_fallback = models.BooleanField(default=False)             # 切换了备用模型
    result_summary = models.CharField(max_length=32, null=True)  # pass/reject/supplement/error
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['case_id', 'created_at']),
            models.Index(fields=['phase_type']),
        ]
```

---

## apps/system — 系统配置

### ConfigVersion（系统配置版本管理）
```python
class ConfigVersion(models.Model):
    config_type = models.CharField(max_length=32)                # sla / notification / model / phase_timeout
    config_key = models.CharField(max_length=64)                 # 具体配置项标识
    version = models.IntegerField()
    value = models.JSONField()                                   # 配置内容快照
    changed_by = models.ForeignKey('organizations.User', null=True, on_delete=models.SET_NULL)
    change_note = models.TextField(null=True)
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
```

---

## 跨 App 引用关系

```
cases.Case
  ├── cases.ClaimReport (OneToOne)
  ├── cases.Attachment[] (FK → Case)
  ├── cases.PolicyLink[] (FK → Case → policies.Policy)
  ├── audit.AuditResult[] (FK → Case)
  ├── sla.SLARecord (OneToOne)
  ├── reports.AuditReport (OneToOne)
  └── organizations.ReviewGroup (via project+product_type)

audit.AuditResult
  ├── audit.RuleResult[] (FK → AuditResult)
  │     └── audit.RuleEvidence[] (FK → RuleResult)
  ├── audit.Intervention[] (FK → Case)
  └── audit.ToolCallRecord[] (FK → Case)

policies.Policy
  └── policies.Product (FK)

rules.AuditRule
  └── rules.RuleVersion[] (FK → AuditRule)
```

---

## 索引清单（汇总）

| Model | 索引字段 |
|-------|---------|
| Case | `insured_id`, `status`, `project_id`, `created_at`, `case_no` |
| Policy | `insured_id, status`, `policy_no` |
| AuditResult | `case_id, policy_link_id` |
| ModelCallLog | `case_id, created_at`, `phase_type` |
| SLARecord | `case_id`, `status, deadline_at` |
| LimitTracker | `ref_id, level` |
| ToolCallRecord | `case_id, tool_name, call_params_hash` |
