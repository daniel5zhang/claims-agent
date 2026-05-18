from django.db import models
import uuid

class Drug(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    drug_code = models.CharField(max_length=64, null=True, blank=True)
    common_name = models.CharField(max_length=256)
    product_name = models.CharField(max_length=256, null=True, blank=True)
    drug_type = models.CharField(max_length=32, null=True, blank=True)
    drug_category = models.CharField(max_length=64, null=True, blank=True)
    is_original = models.BooleanField(default=False)
    is_first_drug = models.BooleanField(default=False)
    is_overseas_medicine = models.BooleanField(default=False)
    target = models.CharField(max_length=256, null=True, blank=True)
    production_factory = models.CharField(max_length=256, null=True, blank=True)
    source = models.CharField(max_length=16, default="readonly_db")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class DrugIndication(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    drug = models.ForeignKey(Drug, on_delete=models.CASCADE)
    disease_name = models.CharField(max_length=256)
    indication_points = models.JSONField(default=list)
    specification_indication = models.TextField(null=True, blank=True)
    month_drug_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    is_charity = models.BooleanField(default=False)
    source = models.CharField(max_length=32, default="readonly_db")
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)


class DrugAuditPoint(models.Model):
    """药品适应症审核要点 — 每条具体的审核规则"""
    id = models.CharField(primary_key=True, max_length=64)
    drug = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name='audit_points')
    indication = models.CharField(max_length=256)  # 适应症名称（如"肺癌"、"甲状腺癌"）
    point_index = models.IntegerField(default=1)   # 第几条审核要点
    point_content = models.TextField()             # 审核要点内容
    point_detail = models.TextField(null=True)     # 详细说明（含医学定义）
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=['drug_id', 'indication'])]
