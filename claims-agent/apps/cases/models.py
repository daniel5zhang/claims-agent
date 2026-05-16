"""Phase 1: 案件数据入口模块 — 核心模型"""
from django.db import models
from apps.organizations.models import User


class Case(models.Model):
    """案件"""
    case_no = models.CharField(max_length=64, unique=True, db_index=True)
    source_system = models.CharField(max_length=3)               # OLD / MAN / API
    source_case_no = models.CharField(max_length=64, null=True, blank=True)
    project = models.ForeignKey("policies.Project", on_delete=models.PROTECT, null=True)
    # 出险人
    insured_id = models.CharField(max_length=64)
    insured_name = models.CharField(max_length=64)
    id_number = models.CharField(max_length=18)
    phone = models.CharField(max_length=20, blank=True, default="")
    # 就诊
    diagnosis = models.CharField(max_length=256, blank=True, default="")
    hospital_name = models.CharField(max_length=256, null=True, blank=True)
    report_date = models.DateTimeField(null=True)
    risk_date = models.DateTimeField(null=True)
    # 理赔
    claim_mode = models.CharField(max_length=16, default="reimbursement")  # direct / reimbursement
    claim_type = models.CharField(max_length=32, default="SP")
    # 状态
    status = models.CharField(max_length=32, default="pending", db_index=True)
    priority = models.CharField(max_length=16, default="normal")
    priority_set_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")
    priority_set_at = models.DateTimeField(null=True)
    # 执行
    max_execution_minutes = models.IntegerField(default=120)
    agent_started_at = models.DateTimeField(null=True)
    # 撤销
    cancelled_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")
    cancelled_at = models.DateTimeField(null=True)
    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["insured_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["project_id"]),
        ]

    def __str__(self):
        return f"{self.case_no} ({self.insured_name})"


class ClaimReport(models.Model):
    """报案信息"""
    case = models.OneToOneField(Case, on_delete=models.CASCADE, related_name="report")
    report_person_name = models.CharField(max_length=64)
    insured_relation = models.CharField(max_length=32, null=True, blank=True)
    report_person_phone = models.CharField(max_length=20, blank=True, default="")
    report_person_sex = models.CharField(max_length=4, null=True, blank=True)
    apply_claim_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True)


class Attachment(models.Model):
    """附件"""
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="attachments")
    file_name = models.CharField(max_length=256)
    storage_path = models.CharField(max_length=512)
    attachment_type = models.CharField(max_length=64, null=True, blank=True)
    file_size = models.IntegerField()
    mime_type = models.CharField(max_length=64, default="application/octet-stream")
    upload_source = models.CharField(max_length=16, default="local")
    created_at = models.DateTimeField(auto_now_add=True)


class PolicyLink(models.Model):
    """案件关联保单"""
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="policy_links")
    policy = models.ForeignKey("policies.Policy", on_delete=models.PROTECT)
    source = models.CharField(max_length=16, default="readonly_db")
    created_at = models.DateTimeField(auto_now_add=True)
