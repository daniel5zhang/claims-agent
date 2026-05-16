from django.db import models
import uuid

class Project(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    project_code = models.CharField(max_length=64)
    project_name = models.CharField(max_length=256)
    company_name = models.CharField(max_length=256, null=True, blank=True)
    project_type = models.CharField(max_length=64, null=True, blank=True)
    claim_type = models.CharField(max_length=64, null=True, blank=True)
    start_date = models.DateField(null=True)
    end_date = models.DateField(null=True)
    project_status = models.CharField(max_length=32, default="0")
    product_name = models.CharField(max_length=256, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Product(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    product_code = models.CharField(max_length=64)
    product_name = models.CharField(max_length=256)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    claim_type = models.CharField(max_length=32, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class InsuranceProduct(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True)
    insurance_code = models.CharField(max_length=64)
    insurance_liability = models.CharField(max_length=256, null=True, blank=True)
    duty_type = models.CharField(max_length=64, null=True, blank=True)
    security_lines = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    deductible_excess = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    waiting_period = models.IntegerField(null=True)
    algorithm_id = models.CharField(max_length=64, null=True)
    pre_existing_disease_ratio = models.DecimalField(max_digits=5, decimal_places=4, null=True)
    not_pre_existing_disease_ratio = models.DecimalField(max_digits=5, decimal_places=4, null=True)
    status = models.CharField(max_length=16, default="active")
    created_at = models.DateTimeField(auto_now_add=True)

class CalculationAlgorithm(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    algorithm_id = models.CharField(max_length=64)
    algorithm_logic = models.TextField(null=True, blank=True)
    algorithm_describe = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Policy(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    policy_no = models.CharField(max_length=64)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True)
    insured_id = models.CharField(max_length=64)
    coverage_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    effective_date = models.DateField(null=True)
    expiry_date = models.DateField(null=True)
    is_renewal = models.BooleanField(default=False)
    status = models.CharField(max_length=32, default="active")
    created_at = models.DateTimeField(auto_now_add=True)

class LimitTracker(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    level = models.CharField(max_length=32)
    ref_id = models.CharField(max_length=64)
    limit_type = models.CharField(max_length=32)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    used_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    source = models.CharField(max_length=32, default="readonly_db")
    updated_at = models.DateTimeField(auto_now=True)
