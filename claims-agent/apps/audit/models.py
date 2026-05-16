"""Phase 3: 审核执行 + 结果模型"""
from django.db import models
from apps.cases.models import Case, PolicyLink


class AuditResult(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE)
    policy_link = models.ForeignKey(PolicyLink, on_delete=models.PROTECT, null=True)
    status = models.CharField(max_length=32, default="running")
    decision = models.CharField(max_length=32, null=True, blank=True)
    pay_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True)


class RuleResult(models.Model):
    audit_result = models.ForeignKey(AuditResult, on_delete=models.CASCADE, related_name="rule_results")
    rule = models.ForeignKey("rules.AuditRule", on_delete=models.PROTECT, null=True)
    result = models.CharField(max_length=32)  # pass/reject/supplement/transferToManual
    reason = models.TextField(blank=True, default="")
    evidence = models.JSONField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Intervention(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE)
    audit_result = models.ForeignKey(AuditResult, null=True, on_delete=models.SET_NULL)
    phase = models.CharField(max_length=64)
    operator = models.ForeignKey("organizations.User", on_delete=models.PROTECT)
    opinion = models.TextField()
    action = models.CharField(max_length=32)  # continue/pause/override
    created_at = models.DateTimeField(auto_now_add=True)


class ToolCallRecord(models.Model):
    case_id = models.CharField(max_length=64)
    phase_type = models.CharField(max_length=64)
    tool_name = models.CharField(max_length=64)
    call_params_hash = models.CharField(max_length=64)
    result = models.JSONField()
    status = models.CharField(max_length=16, default="success")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["case_id", "tool_name", "call_params_hash"])]
