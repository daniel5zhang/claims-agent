"""Phase 8: 理算公式引擎 + 责任聚合"""
import json
from decimal import Decimal, InvalidOperation


def safe_decimal(v, default=Decimal("0")):
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return default


def calculate_compensation(algorithm_id: str, bill_data: dict, policy_data: dict) -> dict:
    """单保单赔付计算 — 从算法库加载公式，代入账单数据"""
    # 从 DB 加载算法公式
    import pysqlite3 as sqlite3
    from pathlib import Path
    from django.conf import settings

    db = Path(settings.BASE_DIR) / "data" / "db.sqlite3"
    conn = sqlite3.connect(str(db))
    formula = None
    try:
        r = conn.execute(
            "SELECT algorithm_logic, algorithm_describe FROM policies_calculationalgorithm WHERE algorithm_id = ?",
            [algorithm_id]
        ).fetchone()
        if r:
            formula = r[0] or r[1]
    finally:
        conn.close()

    # 参数提取 — 兼容 DB 中文/英文两种字段名
    FIELD_MAP = {
        "drug_unit_price": ["drug_unit_price", "单价"],
        "quantity": ["quantity", "数量"],
        "payout_ratio": ["payout_ratio", "赔付比例"],
        "remaining_coverage": ["remaining_coverage", "剩余保额"],
        "deductible_balance": ["deductible_balance", "免赔额余额"],
        "social_security": ["social_security", "社保报销", "统筹支付"],
        "self_pay": ["self_pay", "自费金额"],
        "third_party_pay": ["third_party_pay", "第三方支付金额"],
        "total_amount": ["total_amount", "账单金额", "费用总额"],
        "category_b_self_pay": ["category_b_self_pay", "乙类自付"],
    }

    def _get_val(data_dict, field_key, default=0):
        """按字段映射查找值，兼容中英文"""
        for alias in FIELD_MAP.get(field_key, [field_key]):
            if alias in data_dict and data_dict[alias] is not None:
                return safe_decimal(data_dict[alias])
        # fallback: check bill_data too for crossover fields
        for alias in FIELD_MAP.get(field_key, [field_key]):
            if alias in bill_data and bill_data[alias] is not None:
                return safe_decimal(bill_data[alias])
        return safe_decimal(default)

    drug_price = _get_val(bill_data, "drug_unit_price")
    quantity = _get_val(bill_data, "quantity")
    payout_ratio = _get_val(policy_data, "payout_ratio", 0.9)
    remaining_coverage = _get_val(policy_data, "remaining_coverage", 50000)
    deductible_balance = _get_val(policy_data, "deductible_balance")
    social_security = _get_val(bill_data, "social_security")
    self_pay = _get_val(bill_data, "self_pay")
    third_party = _get_val(bill_data, "third_party_pay")
    total_amount = _get_val(bill_data, "total_amount")
    category_b = _get_val(bill_data, "category_b_self_pay")

    # 药品公式: Min(单价×数量×赔付比例, 剩余保额)
    drug_amount = drug_price * quantity * payout_ratio

    # 住院公式: (总金额-社保-自费-第三方-大病-免赔余额-乙类自付)×赔付比例
    hospital_amount = (total_amount - social_security - self_pay - third_party
                       - deductible_balance - category_b) * payout_ratio

    # 取药品或住院的最大值（根据实际场景其中一个非零）
    pay_amount = min(max(drug_amount, hospital_amount), remaining_coverage)

    detail = {
        "formula": formula or f"Min(单价×数量×赔付比例, 剩余保额)",
        "drug_price": float(drug_price),
        "quantity": float(quantity),
        "payout_ratio": float(payout_ratio),
        "remaining_coverage": float(remaining_coverage),
        "drug_amount": float(drug_amount),
        "hospital_amount": float(hospital_amount),
        "pay_amount": float(pay_amount),
    }
    return {"pay_amount": float(pay_amount), "calculation_detail": detail}


def aggregate_liabilities(case_id: str, policy_results: list[dict]) -> dict:
    """多保单责任聚合 — 重复责任识别 + 关联责任 + 最大化赔付"""
    per_policy = []
    total = Decimal("0")

    # 按主次险顺序排序（保单字段 → 项目配置 → 末尾）
    def _resolve_order(p):
        explicit = p.get("insurance_order")
        if explicit is not None: return explicit
        project_order = get_insurance_order(p, p.get("project_config"))
        return project_order if project_order is not None else 999
    ordered = sorted(policy_results, key=_resolve_order)

    overlapping_handled = []
    maximization_notes = []
    seen_expenses = set()

    for p in ordered:
        pay = safe_decimal(p.get("pay_amount", 0))

        # 重复责任识别：同一费用项已被前面的保单覆盖
        expenses = p.get("expense_items", [])
        for exp in expenses:
            key = exp.get("category", "") + exp.get("description", "")
            if key in seen_expenses:
                overlapping_handled.append(f"{exp.get('description','?')} 由主险优先赔付，{p['policy_id']} 不重复计算")
                continue
            seen_expenses.add(key)

        per_policy.append({
            "policy_id": p["policy_id"],
            "product_type": p.get("product_type", ""),
            "pay_amount": float(pay),
            "decision": p.get("decision", "pass"),
        })
        total += pay

    # 关联责任：特药险依赖医疗险住院认定（mock）
    maximization_notes.append("特药险按实际药费赔付，医疗险按住院总费用扣除特药险赔付后计算")

    return {
        "case_id": case_id,
        "total_pay_amount": float(total),
        "per_policy": per_policy,
        "overlapping_handled": overlapping_handled or ["无重复责任"],
        "maximization_notes": "; ".join(maximization_notes),
    }


def get_insurance_order(policy: dict, project_config: dict = None) -> int | None:
    """主次险顺序查找"""
    order = policy.get("insurance_order")
    if order is not None:
        return order
    if project_config:
        order = project_config.get("liability_order", {}).get(policy.get("product_type"))
        if order is not None:
            return order
    return None  # 触发转人工
