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
