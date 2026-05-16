"""通知分发器 — 钉钉/企微/站内/API回调"""
import json
import logging
from apps.notifications.models import Message

logger = logging.getLogger("notifications")

EVENT_TYPES = [
    "case_supplement", "case_manual", "case_complete_pass", "case_complete_reject",
    "sla_warning", "sla_overdue", "sla_escalate",
    "pharmacy_order_success", "pharmacy_order_fail", "pharmacy_delivered",
    "batch_complete", "batch_fail", "rule_version_published",
]


def dispatch(event_type: str, case_id: str = "", roles: list[str] = None,
             channels: list[str] = None, **kwargs) -> dict:
    """按配置分发通知"""
    results = {}
    channels = channels or ["inapp"]

    if "inapp" in channels:
        results["inapp"] = _send_inapp(event_type, case_id, roles, **kwargs)
    if "dingtalk" in channels:
        results["dingtalk"] = _send_dingtalk(event_type, kwargs.get("message", ""))
    if "wecom" in channels:
        results["wecom"] = _send_wecom(event_type, kwargs.get("message", ""))
    if "api_callback" in channels:
        results["api_callback"] = _api_callback(event_type, kwargs)

    return results


def _send_inapp(event_type: str, case_id: str, roles: list[str] = None, **kwargs) -> str:
    msg = Message.objects.create(
        recipient_id=None,  # TODO: resolve from roles
        title=kwargs.get("title", event_type),
        body=kwargs.get("body", ""),
        case_id=case_id,
    )
    return f"inapp:{msg.id}"


def _send_dingtalk(event_type: str, message: str) -> str:
    logger.info(f"DingTalk: {event_type} - {message[:100]}")
    return "dingtalk:queued"


def _send_wecom(event_type: str, message: str) -> str:
    logger.info(f"WeCom: {event_type} - {message[:100]}")
    return "wecom:queued"


def _api_callback(event_type: str, data: dict) -> str:
    logger.info(f"API Callback: {event_type} - {json.dumps(data, ensure_ascii=False)[:200]}")
    return "callback:queued"
