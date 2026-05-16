"""保单有效期校验钩子 — 当前默认通过，预留后续规则"""
from datetime import date

def validate_policy_status(policy, claim_date: date) -> dict:
    """预留：宽限期/复效中/终止后的校验逻辑"""
    return {"result": "pass", "reason": "policy_status_check_skipped"}
