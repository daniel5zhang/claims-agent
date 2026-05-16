"""案件状态机 + 转人工 + 补材 + SLA"""
from datetime import datetime, timedelta
from django.utils import timezone
from apps.cases.models import Case

VALID_TRANSITIONS = {
    "pending": ["running", "cancelled"],
    "running": ["supplement_required", "manual_review", "completed", "error", "cancelled"],
    "supplement_required": ["running", "cancelled"],
    "manual_review": ["running", "completed", "cancelled"],
    "completed": [],
    "error": ["running", "manual_review", "cancelled"],
    "cancelled": [],
}


def transition(case: Case, new_status: str, operator=None) -> bool:
    if new_status not in VALID_TRANSITIONS.get(case.status, []):
        return False
    case.status = new_status
    if new_status == "cancelled":
        case.cancelled_at = timezone.now()
        case.cancelled_by = operator
    case.save()
    return True


def check_force_manual(case: Case, pay_amount: float = 0, risk_level: str = "normal") -> bool:
    """配置驱动的强制转人工判断"""
    if pay_amount > 50000:
        return True
    if risk_level == "high":
        return True
    return False


def assign_review_group(case: Case):
    """审核组分配 — 按项目+产品+金额+风险"""
    from apps.organizations.models import ReviewGroup
    groups = ReviewGroup.objects.filter(is_active=True)
    for g in groups.order_by("-is_default"):
        if g.project_id and str(g.project_id) != str(case.project_id):
            continue
        if g.product_type and case.claim_type != g.product_type:
            continue
        return g
    return ReviewGroup.objects.filter(is_default=True).first()


def generate_supplement_items(case: Case, rule_results: list[dict]) -> list[dict]:
    """从审核结果生成缺材清单"""
    items = []
    for r in rule_results:
        if r.get("result") == "supplement":
            for item in r.get("missing_items", []):
                items.append({"name": item, "rule": r.get("rule_code", ""), "reason": r.get("reason", "")})
    return items


class SLATracker:
    """SLA 时效追踪"""

    def __init__(self, total_hours: int = 48, warn_hours: int = 4, escalate_hours: int = 8):
        self.total_hours = total_hours
        self.warn_hours = warn_hours
        self.escalate_hours = escalate_hours

    def evaluate(self, started_at, paused_minutes: int = 0) -> dict:
        if started_at is None:
            return {"status": "normal"}
        elapsed = (timezone.now() - started_at).total_seconds() / 3600 - paused_minutes / 60
        remaining = self.total_hours - elapsed
        if remaining <= 0:
            return {"status": "overdue", "elapsed_h": round(elapsed, 1),
                    "action": "escalate", "escalate_action": "notify_supervisor"}
        if remaining <= self.warn_hours:
            return {"status": "warning", "elapsed_h": round(elapsed, 1),
                    "remaining_h": round(remaining, 1), "action": "notify"}
        return {"status": "normal", "elapsed_h": round(elapsed, 1),
                "remaining_h": round(remaining, 1)}
