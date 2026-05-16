from django.db import models
import uuid

class Disease(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    disease_name = models.CharField(max_length=256)
    disease_code = models.CharField(max_length=32, null=True, blank=True)
    disease_type = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
