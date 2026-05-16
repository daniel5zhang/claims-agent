from huey import crontab
from huey.contrib.djhuey import db_periodic_task
from datetime import timedelta
from django.utils import timezone

@db_periodic_task(crontab(minute='0', hour='2'))
def cleanup_old_logs():
    """Delete ModelCallLog and SLAEvent older than 7 days"""
    cutoff = timezone.now() - timedelta(days=7)
    # ModelCallLog will be in apps.evaluation.models
    try:
        from apps.evaluation.models import ModelCallLog
        ModelCallLog.objects.filter(created_at__lt=cutoff).delete()
    except Exception:
        pass
    try:
        from apps.sla.models import SLAEvent
        SLAEvent.objects.filter(created_at__lt=cutoff).delete()
    except Exception:
        pass
