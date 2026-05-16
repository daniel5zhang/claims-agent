"""规则版本管理 + 系统配置版本管理"""
from django.utils import timezone


def publish_rule_version(rule, new_content: str, changed_by=None, strategy: str = "immediate"):
    """发布规则新版本"""
    from .models import RuleVersion
    latest = rule.versions.order_by("-version").first()
    new_ver = _bump_version(latest.version if latest else "v0.0")
    RuleVersion.objects.filter(rule=rule, is_current=True).update(is_current=False)
    v = RuleVersion.objects.create(
        rule=rule, version=new_ver, prompt_content=new_content,
        is_current=True, changed_by=changed_by,
    )
    return v


def rollback_rule(rule, target_version: str):
    """回滚到指定版本"""
    from .models import RuleVersion
    target = rule.versions.get(version=target_version)
    RuleVersion.objects.filter(rule=rule, is_current=True).update(is_current=False)
    target.is_current = True
    target.save()
    return target


def save_config_version(config_type: str, config_key: str, value: dict, changed_by=None):
    """系统配置版本化"""
    from apps.organizations.models import User
    import uuid
    class ConfigVersion(models.Model):
        pass  # already defined in system app
    # Use existing model
    try:
        from django.apps import apps
        CV = apps.get_model('system', 'ConfigVersion')
    except Exception:
        return None
    CV.objects.filter(config_type=config_type, config_key=config_key, is_current=True).update(is_current=False)
    v = CV.objects.create(
        config_type=config_type, config_key=config_key,
        version=_next_config_version(config_type, config_key),
        value=value, changed_by=changed_by, is_current=True,
    )
    return v


def _bump_version(v: str) -> str:
    parts = v.lstrip("v").split(".")
    major, minor = int(parts[0]), int(parts[1])
    minor += 1
    if minor >= 10:
        major += 1
        minor = 0
    return f"v{major}.{minor}"


def _next_config_version(config_type: str, config_key: str) -> int:
    try:
        from django.apps import apps
        CV = apps.get_model('system', 'ConfigVersion')
        last = CV.objects.filter(config_type=config_type, config_key=config_key).order_by("-version").first()
        return (last.version + 1) if last else 1
    except Exception:
        return 1

# django stub
from django.db import models
