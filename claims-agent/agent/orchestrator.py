"""Agent Orchestrator — 参考 Claude Code query.ts while(true) 模式"""
import asyncio
import json
import time
import logging
from dataclasses import dataclass, field
from openai import OpenAI
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("agent")


@dataclass
class AgentContext:
    case_id: str
    messages: list = field(default_factory=list)
    policies: list = field(default_factory=list)
    current_phase: str = ""
    phase_results: dict = field(default_factory=dict)
    human_interventions: list = field(default_factory=list)
    max_turns: int = 30
    turn_count: int = 0
    errors: list = field(default_factory=list)
    aborted: bool = False


def _get_client(model: str) -> OpenAI:
    return OpenAI(
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.DASHSCOPE_BASE_URL,
    )


async def run_agent(case_id: str, policy_ids: list[str]) -> dict:
    """
    主循环: while True → 调模型 → 收集 tools → 执行 → 追加结果 → 继续
    返回: {"decision": "pass|reject|...", "total_amount": 0, "details": {...}}
    """
    ctx = AgentContext(case_id=case_id)
    client = _get_client(settings.PRIMARY_MODEL)
    model = settings.PRIMARY_MODEL

    try:
        # Phase 0: 案件解析 + 保单发现
        _run_phase_sync(ctx, "phase_0_discovery", case_id, policy_ids)

        # Phase 1-5: 并行执行每个保单
        policy_results = await asyncio.gather(*[
            _run_policy_pipeline(ctx, pid) for pid in policy_ids
        ])

        # Phase 7: 责任聚合
        final = await _run_aggregation(ctx, policy_results)
        return final

    except Exception as e:
        logger.exception(f"Agent failed: {e}")
        return {"decision": "error", "reason": str(e), "total_amount": 0}


def _run_phase_sync(ctx: AgentContext, phase: str, case_id: str, policy_ids: list[str]):
    """同步阶段（查库操作）"""
    ctx.current_phase = phase
    # Phase 0: 查案件信息 + 保单发现
    from apps.cases.models import Case
    from apps.policies.services.policy_discovery import discover_policies
    from datetime import date

    case = Case.objects.get(id=case_id)
    ctx.policies = policy_ids


async def _run_policy_pipeline(ctx: AgentContext, policy_id: str) -> dict:
    """单保单流水线: raise Model → 收集 tools → 执行 → 循环"""
    from apps.cases.models import Case
    case = Case.objects.get(id=ctx.case_id)

    # 构建工具 + 系统提示
    tools = _build_policy_tools(case.claim_mode, case.claim_type)
    system_prompt = _build_system_prompt(ctx)

    messages = [{"role": "system", "content": system_prompt}]
    messages.append({
        "role": "user",
        "content": f"审核案件 {case.case_no}，保单 {policy_id}。"
                   f"诊断: {case.diagnosis}。请按 Phase 顺序执行审核。"
    })

    client = _get_client(settings.PRIMARY_MODEL)
    model = settings.PRIMARY_MODEL
    tool_results = []

    for turn in range(ctx.max_turns):
        ctx.turn_count += 1
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                temperature=0.1,
            )
        except Exception as e:
            # 重试 + 备用模型
            if _is_rate_limit(e):
                await asyncio.sleep(_backoff(turn))
                continue
            try:
                client = _get_client(settings.FALLBACK_MODEL)
                model = settings.FALLBACK_MODEL
                resp = client.chat.completions.create(
                    model=model, messages=messages, tools=tools, temperature=0.1
                )
            except Exception:
                ctx.errors.append(str(e))
                return {"policy_id": policy_id, "decision": "error", "reason": str(e)}

        msg = resp.choices[0].message
        if msg.tool_calls is None:
            # 模型给出最终回复
            return _parse_policy_result(msg.content, policy_id)

        # 添加 assistant 消息
        tool_msgs = []
        for tc in msg.tool_calls:
            tool_msgs.append({
                "id": tc.id, "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            })
        messages.append({"role": "assistant", "content": msg.content, "tool_calls": tool_msgs})

        # 执行工具调用
        for tc in msg.tool_calls:
            result = await _execute_tool(tc.function.name, json.loads(tc.function.arguments), ctx)
            tool_results.append({"tool": tc.function.name, "result": result})
            messages.append({
                "role": "tool", "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

    return {"policy_id": policy_id, "decision": "transferToManual", "reason": "max_turns_exceeded"}


def _build_policy_tools(claim_mode: str, claim_type: str) -> list[dict]:
    """按险种责任动态构建工具列表"""
    tools = [
        _tool_def("get_case_info", "获取案件基础信息", {"case_id": "string"}),
        _tool_def("verify_on_ins", "校验保单在保状态", {"policy_id": "string"}),
        _tool_def("match_drug", "药品库匹配", {"drug_name": "string"}),
        _tool_def("match_hospital", "医院库匹配", {"hospital_name": "string"}),
        _tool_def("match_disease", "疾病 ICD-10 标准化", {"disease_name": "string"}),
        _tool_def("run_audit_rule", "执行审核规则", {"rule_code": "string", "archive": "object"}),
        _tool_def("calculate_compensation", "计算赔付金额", {"algorithm_id": "string", "bill_data": "object"}),
    ]
    if claim_mode == "direct":
        tools.append(_tool_def("match_pharmacy", "匹配履约药房", {"drug_id": "string", "location": "string"}))
    return tools


def _tool_def(name: str, desc: str, params: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": {k: {"type": v} for k, v in params.items()},
                "required": list(params.keys()),
            },
        },
    }


async def _execute_tool(name: str, args: dict, ctx: AgentContext) -> dict:
    """工具执行 + 幂等保护"""
    from agent.tools.ocr_tools import ocr_classify, ocr_extract
    from agent.tools.extraction_tools import extract_medical_bill, extract_medical_info, extract_prescription
    from agent.tools.matching_tools import match_drug, match_hospital, match_disease, match_compared_drugs, verify_on_ins, get_product_terms
    from agent.tools.archive_tools import generate_archive, query_history_claims, generate_archive_json
    from agent.tools.audit_tools import (run_audit_rule, check_duplicate_claim,
        check_material_complete, check_waiting_period, run_indication_audit)
    from agent.tools.calculation_tools import calculate_compensation, aggregate_liabilities
    from agent.tools.fulfillment_tools import (match_pharmacy, create_pharmacy_order,
        track_fulfillment, notify_insurer, check_direct_payment_auth)

    tool_map = {
        "get_case_info": lambda: {"case_no": ctx.case_id, "status": "ok"},
        "verify_on_ins": lambda: verify_on_ins(args.get("policy_id", "")),
        "match_drug": lambda: match_drug(args.get("drug_name", "")),
        "match_hospital": lambda: match_hospital(args.get("hospital_name", "")),
        "match_disease": lambda: match_disease(args.get("disease_name", "")),
        "match_compared_drugs": lambda: match_compared_drugs(args.get("drug_name", "")),
        "get_product_terms": lambda: get_product_terms(args.get("product_id", "")),
        "run_audit_rule": lambda: run_audit_rule(
            args.get("rule_code", ""), args.get("archive", {}),
            args.get("history", {}), args.get("matched_results", {}), args.get("case_info", {})),
        "calculate_compensation": lambda: calculate_compensation(
            args.get("algorithm_id", ""), args.get("bill_data", {}), args.get("policy_data", {})),
        "aggregate_liabilities": lambda: aggregate_liabilities(
            ctx.case_id, args.get("policy_results", [])),
        "match_pharmacy": lambda: match_pharmacy(
            args.get("drug_id", ""), args.get("location", ""), args.get("quantity", 1)),
        "create_pharmacy_order": lambda: create_pharmacy_order(
            ctx.case_id, args.get("policy_id", ""), args.get("drug_id", ""),
            args.get("pharmacy_id", ""), args.get("quantity", 1)),
        "track_fulfillment": lambda: track_fulfillment(args.get("order_id", "")),
        "notify_insurer": lambda: notify_insurer(
            ctx.case_id, args.get("decision", ""), args.get("amount", 0)),
        "ocr_classify": lambda: ocr_classify(args.get("attachments", [])),
        "ocr_extract": lambda: ocr_extract(args.get("attachments", [])),
        "extract_medical_bill": lambda: extract_medical_bill(args.get("raw_text", ""), args.get("attachment_id", "")),
        "extract_medical_info": lambda: extract_medical_info(args.get("raw_text", ""), args.get("attachment_id", "")),
        "extract_prescription": lambda: extract_prescription(args.get("raw_text", ""), args.get("attachment_id", "")),
        "generate_archive": lambda: generate_archive(args.get("ocr_results", []), args.get("case_info", {})),
        "query_history_claims": lambda: query_history_claims(args.get("insured_id", "")),
        "generate_archive_json": lambda: generate_archive_json(args.get("archive", {})),
        "check_duplicate_claim": lambda: check_duplicate_claim(
            args.get("current_case", {}), args.get("history_cases", [])),
        "check_material_complete": lambda: check_material_complete(
            args.get("attachments", []), args.get("purchase_type", "outside_pharmacy")),
        "check_waiting_period": lambda: check_waiting_period(
            args.get("policy_effective_date"), args.get("claim_date"),
            args.get("waiting_days", 30), args.get("is_renewal", False)),
        "run_indication_audit": lambda: run_indication_audit(
            args.get("drug_name", ""), args.get("archive", {})),
    }
    handler = tool_map.get(name)
    if handler:
        return handler()
    return {"error": f"unknown tool: {name}"}


def _build_system_prompt(ctx: AgentContext) -> str:
    return f"""你是保险理赔 AI 审核专家。按 Phase 0→1→2→3→4→5→6→7 顺序执行审核。
案件 ID: {ctx.case_id}
输出格式: {{"decision":"pass|reject|supplement|transferToManual","reason":"...","amount":0}}
审核原则: 准确、基于证据、不做推断。缺少材料时标记 supplement。有歧义时标记 transferToManual。"""


def _parse_policy_result(content: str | None, policy_id: str) -> dict:
    try:
        import json
        r = json.loads(content or "{}")
        r["policy_id"] = policy_id
        return r
    except json.JSONDecodeError:
        return {"policy_id": policy_id, "decision": "error", "reason": "parse_failed"}


async def _run_aggregation(ctx: AgentContext, policy_results: list[dict]) -> dict:
    """Phase 7: 责任聚合"""
    total = sum(float(r.get("amount", 0)) for r in policy_results)
    decisions = {r.get("decision") for r in policy_results}
    if "reject" in decisions:
        final = "reject"
    elif "transferToManual" in decisions:
        final = "transferToManual"
    elif "supplement" in decisions:
        final = "supplement"
    elif all(d == "pass" for d in decisions):
        final = "pass"
    else:
        final = "transferToManual"
    return {"decision": final, "total_amount": total, "per_policy": policy_results}


def _is_rate_limit(e: Exception) -> bool:
    return "429" in str(e) or "rate" in str(e).lower()


def _backoff(turn: int) -> float:
    return min(1.0 * (2 ** turn), 8.0)
