from django.db import models
import uuid

class Hospital(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=256)
    hospital_level = models.CharField(max_length=32, null=True, blank=True)
    hospital_nature = models.CharField(max_length=64, null=True, blank=True)
    specialty_nature = models.CharField(max_length=64, null=True, blank=True)
    province = models.CharField(max_length=64, null=True, blank=True)
    city = models.CharField(max_length=64, null=True, blank=True)
    district = models.CharField(max_length=64, null=True, blank=True)
    source = models.CharField(max_length=16, default="readonly_db")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
