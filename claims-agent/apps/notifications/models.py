from django.db import models

class NotificationTemplate(models.Model):
    name = models.CharField(max_length=128)
    channel = models.CharField(max_length=32)
    title_template = models.CharField(max_length=256, null=True, blank=True)
    body_template = models.TextField()
    is_builtin = models.BooleanField(default=False)

class NotificationConfig(models.Model):
    project = models.ForeignKey("policies.Project", null=True, on_delete=models.CASCADE)
    product_type = models.CharField(max_length=64, null=True, blank=True)
    event_type = models.CharField(max_length=64)
    roles = models.JSONField(default=list)
    channels = models.JSONField(default=list)
    template = models.ForeignKey(NotificationTemplate, on_delete=models.PROTECT, null=True)
    is_active = models.BooleanField(default=True)

class Message(models.Model):
    recipient = models.ForeignKey("organizations.User", null=True, on_delete=models.CASCADE, related_name="messages")
    title = models.CharField(max_length=256)
    body = models.TextField()
    case_id = models.CharField(max_length=64, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
