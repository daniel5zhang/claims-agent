from django.db import models

class AuditReport(models.Model):
    case = models.OneToOneField("cases.Case", on_delete=models.PROTECT)
    phases = models.JSONField(default=dict)
    rule_results = models.JSONField(default=dict)
    interventions = models.JSONField(default=list)
    calculation_detail = models.JSONField(default=dict)
    final_decision = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

class DocumentTemplate(models.Model):
    project = models.ForeignKey("policies.Project", null=True, on_delete=models.SET_NULL)
    product_type = models.CharField(max_length=64, null=True, blank=True)
    recipient = models.CharField(max_length=32)
    doc_type = models.CharField(max_length=64)
    template_content = models.TextField()
    output_format = models.CharField(max_length=16, default="pdf")
    trigger = models.CharField(max_length=32, default="auto_on_complete")
    is_active = models.BooleanField(default=True)

class GeneratedDocument(models.Model):
    case = models.ForeignKey("cases.Case", on_delete=models.CASCADE)
    template = models.ForeignKey(DocumentTemplate, on_delete=models.PROTECT, null=True)
    content = models.TextField()
    output_file = models.CharField(max_length=256, null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True)

class ReportTemplate(models.Model):
    name = models.CharField(max_length=128)
    report_type = models.CharField(max_length=32)
    output_format = models.CharField(max_length=16, default="excel")
    is_builtin = models.BooleanField(default=False)

class GeneratedReport(models.Model):
    template = models.ForeignKey(ReportTemplate, on_delete=models.PROTECT)
    params = models.JSONField(default=dict)
    file_path = models.CharField(max_length=256)
    generated_by = models.ForeignKey("organizations.User", on_delete=models.PROTECT, null=True)
    generated_at = models.DateTimeField(auto_now_add=True)
