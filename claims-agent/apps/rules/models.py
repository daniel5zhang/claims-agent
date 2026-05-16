from django.db import models
import uuid

class AuditRule(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    rule_code = models.CharField(max_length=64, unique=True)
    rule_name = models.CharField(max_length=256)
    rule_description = models.TextField(null=True, blank=True)
    layer = models.IntegerField(default=2)
    priority = models.IntegerField(default=0)
    is_blocking = models.BooleanField(default=False)
    liability_types = models.JSONField(default=list)
    primary_model = models.CharField(max_length=64, default="qwen3.6-plus")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class RuleVersion(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    rule = models.ForeignKey(AuditRule, on_delete=models.CASCADE)
    version = models.CharField(max_length=16)
    prompt_content = models.TextField()
    primary_model = models.CharField(max_length=64, null=True)
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class PromptTemplate(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    interface_code = models.CharField(max_length=64)
    interface_type = models.CharField(max_length=64, null=True)
    interface_name = models.CharField(max_length=256, null=True)
    prompt_content = models.TextField()
    primary_model = models.CharField(max_length=64, null=True)
    backup_model = models.CharField(max_length=256, null=True)
    versions = models.CharField(max_length=16, default="1")
    effective = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
