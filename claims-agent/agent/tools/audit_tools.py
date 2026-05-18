"""Phase 7: 审核规则引擎 — 16条规则 + 元规则"""
import json
from pathlib import Path
from openai import OpenAI
from django.conf import settings
from datetime import date, timedelta

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompts" / "audit"

RULE_LAYERS = {
    1: ["1.1_identity", "1.2_insurance_period", "2.1_material_complete"],
    2: ["2.2.1_id_validity", "2.2.2_prescription_validity", "2.2.3_medical_settlement",
        "2.2.4_hospital_bill", "1.3.1_drug_match", "1.3.2_special_disease_whitelist",
        "1.4_hospital_qualification", "3.1_preexisting_disease",
        "drug_verify", "coverage_time_verify"],
    3: ["4.1_minor", "4.2_death"],
    4: ["3.2_calculation"],
}


def _get_client():
    return OpenAI(api_key=settings.DASHSCOPE_API_KEY, base_url=settings.DASHSCOPE_BASE_URL)


def _load_rule_prompt(rule_code: str) -> str:
    p = PROMPT_DIR / rule_code / "v1.txt"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _load_drug_audit_points(drug_name: str, disease: str) -> list[dict]:
    """加载药品专属审核要点"""
    from apps.drugs.models import Drug, DrugAuditPoint
    drug = Drug.objects.filter(common_name__icontains=drug_name[:6]).first()
    if not drug: return []
    points = DrugAuditPoint.objects.filter(drug=drug, is_active=True)
    if disease:
        # Match: disease contains indication keyword (e.g. "非小细胞肺癌" contains "肺癌")
        indications = list(points.values_list('indication', flat=True).distinct())
        for ind in indications:
            if ind and len(ind) >= 2 and ind in disease:
                points = points.filter(indication=ind)
                break
    return [{'point_index': p.point_index, 'point_content': p.point_content,
             'indication': p.indication} for p in points[:10]]


def _safe_json(text: str, default=None):
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except (json.JSONDecodeError, ValueError):
        pass
    return default or {}


def run_audit_rule(rule_code: str, archive: dict, history: dict = None,
                   matched_results: dict = None, case_info: dict = None) -> dict:
    """执行单条审核规则"""
    prompt = _load_rule_prompt(rule_code)
    if not prompt:
        return {"result": "pass", "reason": f"rule {rule_code} prompt not found", "rule_code": rule_code}

    # 构建上下文
    context = f"""<客户理赔案件档案>
{json.dumps(archive, ensure_ascii=False)}
</客户理赔案件档案>

<历史案件情况>
{json.dumps(history or {}, ensure_ascii=False)}
</历史案件情况>

<匹配结果>
{json.dumps(matched_results or {}, ensure_ascii=False)}
</匹配结果>

<案件基础信息>
{json.dumps(case_info or {}, ensure_ascii=False)}
</案件基础信息>

请执行规则 {rule_code} 的审核，严格按上述规则判定。"""

    # flash for simple rules, plus for complex reasoning
    model = settings.FLASH_MODEL if rule_code.startswith(("1.1","1.2","2.1","2.2","3.2","drug_verify","coverage_time")) else settings.PRIMARY_MODEL
    client = _get_client()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": prompt},
                      {"role": "user", "content": context}],
            temperature=0.1, max_tokens=512,
        )
        result = _safe_json(resp.choices[0].message.content,
                           {"result": "error", "reason": "parse_failed"})
        result["rule_code"] = rule_code
        return result
    except Exception as e:
        return {"rule_code": rule_code, "result": "error", "reason": str(e)}


def run_all_audit_rules(archive: dict, history: dict = None,
                        matched_results: dict = None, case_info: dict = None) -> dict:
    """按层级执行全部审核规则，返回汇总矩阵"""
    results = []

    for layer in [1, 2, 3, 4]:
        for rule_code in RULE_LAYERS.get(layer, []):
            r = run_audit_rule(rule_code, archive, history, matched_results, case_info)
            results.append(r)
            # 层1阻断：任一 reject 则终止
            if layer == 1 and r.get("result") == "reject":
                return _build_matrix(results)

    return _build_matrix(results)


def check_duplicate_claim(current_case: dict, history_cases: list[dict]) -> dict:
    """重复报案检测"""
    for hist in history_cases:
        if (hist.get("insured_id") == current_case.get("insured_id")
                and _overlaps(hist.get("treatment_period", ""), current_case.get("treatment_period", ""))
                and hist.get("drug_name") == current_case.get("drug_name")):
            return {"result": "warning", "reason": "疑似重复报案", "related_case_id": hist.get("case_id")}
    return {"result": "pass"}


def check_material_complete(attachments: list, purchase_type: str) -> dict:
    """材料完整性规则 — 院内/院外不同要求"""
    rules = {
        "outside_pharmacy": ["处方原件", "购药发票"],
        "outpatient": ["处方或医嘱单", "门诊费用清单"],
        "inpatient": ["医嘱单", "医保结算单", "住院费用清单"],
    }
    required = rules.get(purchase_type, rules["outside_pharmacy"])
    att_types = {a.get("attachment_type", "") for a in attachments}
    missing = [item for item in required if not any(item in t for t in att_types)]

    if purchase_type == "outpatient":
        if "处方" in str(att_types) or "医嘱单" in str(att_types):
            if "处方" not in str(att_types):
                missing = [m for m in missing if m != "处方或医嘱单"]
            elif "医嘱单" not in str(att_types):
                missing = [m for m in missing if m != "处方或医嘱单"]

    if missing:
        return {"result": "supplement", "missing_items": missing,
                "reason": f"缺少材料: {', '.join(missing)}"}
    return {"result": "pass"}


def check_waiting_period(policy_effective_date, claim_date, waiting_days: int = 30,
                          is_renewal: bool = False, renewal_exempt: bool = True) -> dict:
    """等待期判断"""
    if is_renewal and renewal_exempt:
        return {"result": "pass", "reason": "续保豁免等待期"}
    if isinstance(claim_date, str):
        claim_date = date.fromisoformat(claim_date[:10])
    if isinstance(policy_effective_date, str):
        policy_effective_date = date.fromisoformat(policy_effective_date[:10])
    elapsed = (claim_date - policy_effective_date).days
    if elapsed >= waiting_days:
        return {"result": "pass", "reason": f"已过{waiting_days}天等待期"}
    return {"result": "reject", "reason": f"等待期未满({elapsed}/{waiting_days}天)"}


def run_indication_audit(drug_name: str, archive: dict, case_info: dict = None) -> dict:
    """适应症审核要点 — 加载药品专属规则逐条审核"""
    # Load drug-specific audit points
    disease = (archive.get('diagnosis_info', {}).get('disease', '') or
               (case_info or {}).get('diagnosis', ''))
    drug_points = _load_drug_audit_points(drug_name, disease)

    if not drug_points:
        # Fallback: generic prompt
        prompt = _load_rule_prompt("1.3.1_drug_match")
        client = _get_client()
        try:
            resp = client.chat.completions.create(
                model=settings.PRIMARY_MODEL,
                messages=[{"role": "system", "content": prompt or "审核药品适应症"},
                          {"role": "user", "content": f"药品: {drug_name}\n档案: {json.dumps(archive, ensure_ascii=False)}"}],
                temperature=0.1, max_tokens=2048,
            )
            return _safe_json(resp.choices[0].message.content, {"result": "pass", "drug_name": drug_name})
        except Exception as e:
            return {"result": "error", "drug_name": drug_name, "reason": str(e)}

    # Build drug-specific audit prompt
    points_text = "\n".join([f"  {p['point_index']}. {p['point_content']}" for p in drug_points])
    prompt = f"""你是肿瘤特药理赔审核专家。请逐条审核以下{len(drug_points)}个审核要点，每条返回 pass 或 reject 及原因。

<药品审核要点>
{points_text}
</药品审核要点>

<患者档案>
{json.dumps(archive, ensure_ascii=False)}
</患者档案>

审核原则:
1. 每条要点必须基于患者档案中的证据判定，不做推断
2. 缺少证据 → reject，注明"证据不足: ..."
3. 有证据且符合 → pass
4. 所有要点通过才整体 pass

输出格式: {{"result":"pass|reject","reason":"整体判定","points":[{{"index":1,"result":"pass|reject","reason":"..."}}]}}"""

    client = _get_client()
    try:
        resp = client.chat.completions.create(
            model=settings.PRIMARY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=2048,
        )
        return _safe_json(resp.choices[0].message.content, {"result": "pass", "drug_name": drug_name})
    except Exception as e:
        return {"result": "error", "drug_name": drug_name, "reason": str(e)}


def _build_matrix(results: list[dict]) -> dict:
    """汇总矩阵 — 聚合所有规则结果"""
    rejects = [r for r in results if r.get("result") == "reject"]
    supplements = [r for r in results if r.get("result") == "supplement"]
    transfers = [r for r in results if r.get("result") == "transferToManual"]

    if rejects:
        final = "reject"
    elif transfers:
        final = "transferToManual"
    elif supplements:
        final = "supplement"
    else:
        final = "pass"

    return {
        "final_decision": final,
        "rule_results": results,
        "pass_count": sum(1 for r in results if r.get("result") == "pass"),
        "reject_count": len(rejects),
        "supplement_count": len(supplements),
        "transfer_count": len(transfers),
        "reject_reasons": [r.get("reason", "") for r in rejects],
        "supplement_items": [r.get("missing_items", []) for r in supplements],
    }


def _overlaps(a, b):
    return bool(a and b)
