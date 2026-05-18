"""评测数据模型"""
from django.db import models

class EvalAnnotation(models.Model):
    """审核要点标注 — AI vs 人工"""
    annotation_id = models.CharField(max_length=64, unique=True)
    case_id = models.CharField(max_length=64, db_index=True)
    brand_name = models.CharField(max_length=256, null=True)
    generic_name = models.CharField(max_length=256, null=True)
    audit_point = models.TextField(null=True)
    audit_result = models.CharField(max_length=16, null=True)  # AI 结果
    point_result = models.CharField(max_length=16, null=True)  # 最终结果
    manual_review = models.CharField(max_length=16, null=True)
    analyse_result = models.JSONField(null=True)
    audit_point_detail = models.TextField(null=True)
    indication = models.CharField(max_length=256, null=True)
    modify_desc = models.TextField(null=True)


class EvalCase(models.Model):
    """评测案件"""
    case_id = models.CharField(max_length=64, unique=True, db_index=True)
    inner_case_no = models.CharField(max_length=64, null=True)
    insured_id = models.CharField(max_length=64, null=True)
    project_id = models.CharField(max_length=64, null=True)
    claim_status = models.CharField(max_length=32, null=True)
    report_date = models.DateTimeField(null=True)
    pay_total = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    claim_total = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    preexisting_disease = models.CharField(max_length=16, null=True)
    raw_data = models.JSONField(default=dict)


class EvalPolicy(models.Model):
    """评测保单"""
    policy_id = models.CharField(max_length=64, unique=True, db_index=True)
    policy_no = models.CharField(max_length=64, null=True)
    project_id = models.CharField(max_length=64, null=True)
    insurance_start_time = models.DateTimeField(null=True)
    insurance_end_time = models.DateTimeField(null=True)
    raw_data = models.JSONField(default=dict)


class EvalProduct(models.Model):
    """评测保险产品"""
    product_id = models.CharField(max_length=64, unique=True)
    project_id = models.CharField(max_length=64, null=True, db_index=True)
    insurance_liability = models.CharField(max_length=256, null=True)
    pre_existing_disease_ratio = models.DecimalField(max_digits=5, decimal_places=4, null=True)
    not_pre_existing_disease_ratio = models.DecimalField(max_digits=5, decimal_places=4, null=True)
    deductible_excess = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    waiting_period = models.IntegerField(null=True)
    algorithm_id = models.CharField(max_length=64, null=True)
    raw_data = models.JSONField(default=dict)


class EvalAudit(models.Model):
    """评测审核记录"""
    case_id = models.CharField(max_length=64, db_index=True)
    audit_type = models.CharField(max_length=32, null=True)
    audit_conclusion = models.CharField(max_length=32, null=True)
    audit_opinion = models.TextField(null=True)
    auditor = models.CharField(max_length=64, null=True)
    audit_time = models.DateTimeField(null=True)
    raw_data = models.JSONField(default=dict)

    class Meta:
        indexes = [models.Index(fields=['case_id', 'audit_type'])]


class EvalDrugRel(models.Model):
    """产品→药品映射（药单）"""
    product_id = models.CharField(max_length=64, db_index=True)
    drug_id = models.CharField(max_length=64, null=True)
    third_drug_common_name = models.CharField(max_length=256, null=True)
    third_drug_name = models.CharField(max_length=256, null=True)
    third_spec = models.CharField(max_length=128, null=True)
    reimbursement_type = models.CharField(max_length=16, null=True)
    raw_data = models.JSONField(default=dict)


class EvalCaseDrugPoint(models.Model):
    """案件药品审核要点 — 逐药品逐要点人工标注"""
    case_id = models.CharField(max_length=64, db_index=True)
    product_drug_list_option_id = models.CharField(max_length=64, null=True)
    drug_id = models.CharField(max_length=64, null=True)
    auditor = models.CharField(max_length=64, null=True)
    audit_point_conclusion = models.CharField(max_length=16, null=True)  # 1=pass, 0=fail
    type_of_audit_np = models.CharField(max_length=16, null=True)
    audit_detail = models.TextField(null=True)
    raw_data = models.JSONField(default=dict)


class EvalAuditPointDetail(models.Model):
    """审核要点明细 — 更细粒度标注"""
    attachment_audit_detail_id = models.CharField(max_length=64, null=True, db_index=True)
    sku_id = models.CharField(max_length=64, null=True)
    audit_point = models.TextField(null=True)
    audit_detail = models.TextField(null=True)
    audit_result = models.CharField(max_length=16, null=True)
    manual_review = models.CharField(max_length=16, null=True)
    not_pass_type = models.CharField(max_length=16, null=True)
    review_detail = models.TextField(null=True)
    raw_data = models.JSONField(default=dict)
