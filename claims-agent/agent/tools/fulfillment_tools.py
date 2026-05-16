"""Phase 9: 直赔履约 — 药房匹配 + 下单 + 追踪 + 保司确认 (mock)"""
import uuid


class PharmacyAdapter:
    """药房网络接口 — mock"""

    def match(self, drug_id: str, location: str = "", quantity: int = 1) -> list[dict]:
        return [{
            "pharmacy_id": f"PHARM-{uuid.uuid4().hex[:8]}",
            "name": "圆心大药房（mock）",
            "distance_km": 2.3,
            "stock": 50,
            "is_partner": True,
            "score": 95.0,
            "price": 1280.0,
        }]

    def create_order(self, pharmacy_id: str, drug_id: str, quantity: int,
                     idempotency_key: str = "") -> dict:
        return {
            "order_id": f"ORD-{uuid.uuid4().hex[:8]}",
            "pharmacy_id": pharmacy_id,
            "idempotency_key": idempotency_key,
            "status": "confirmed",
            "estimated_delivery": "2026-05-18",
        }

    def get_order_status(self, order_id: str) -> dict:
        return {"order_id": order_id, "status": "delivered"}

    def get_logistics(self, order_id: str) -> dict:
        return {"order_id": order_id, "tracking_no": "SF1234567890", "status": "运输中"}


class InsurerAdapter:
    """保司确认接口 — mock"""

    def notify(self, case_id: str, decision: str, amount: float) -> dict:
        return {"case_id": case_id, "decision": decision, "insurer_status": "acknowledged"}

    def get_confirmation(self, case_id: str) -> dict:
        return {"case_id": case_id, "confirmed": True, "confirmed_at": "2026-05-17"}


# 全局单例
pharmacy_adapter = PharmacyAdapter()
insurer_adapter = InsurerAdapter()


def match_pharmacy(drug_id: str, location: str = "", quantity: int = 1) -> dict:
    """药房匹配 — 按 PharmacySelectionConfig 评分"""
    candidates = pharmacy_adapter.match(drug_id, location, quantity)
    if not candidates:
        return {"matched": False, "reason": "无可用药房"}
    best = max(candidates, key=lambda c: c["score"])
    return {"matched": True, "pharmacy": best, "candidates": candidates}


def create_pharmacy_order(case_id: str, policy_id: str, drug_id: str,
                          pharmacy_id: str, quantity: int) -> dict:
    """下单 — 幂等 key"""
    key = f"{case_id}-{policy_id}-{drug_id}"
    return pharmacy_adapter.create_order(pharmacy_id, drug_id, quantity, idempotency_key=key)


def track_fulfillment(order_id: str) -> dict:
    """履约追踪"""
    status = pharmacy_adapter.get_order_status(order_id)
    logistics = pharmacy_adapter.get_logistics(order_id)
    return {"order_id": order_id, "status": status["status"], "logistics": logistics}


def notify_insurer(case_id: str, decision: str, amount: float) -> dict:
    """推送审核结果到保司"""
    return insurer_adapter.notify(case_id, decision, amount)


def check_direct_payment_auth(auth_valid_days: int = 30, days_passed: int = 0,
                               warn_before_days: int = 7) -> dict:
    """直赔授权有效期预警"""
    remaining = auth_valid_days - days_passed
    if remaining <= 0:
        return {"status": "expired", "remaining_days": remaining}
    if remaining <= warn_before_days:
        return {"status": "warning", "remaining_days": remaining, "action": "notify_reviewer"}
    return {"status": "valid", "remaining_days": remaining}
