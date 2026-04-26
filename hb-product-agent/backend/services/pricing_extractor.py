"""
定价逻辑提取器 — 从历史方案中提取定价方法和参数

输入: Scheme (schemes 表) + SchemeItems (scheme_items 表)
输出: PricingLogic + PricingRules (结构化JSON + 文字描述)

提取管道:
  1. _rule_extract()  — 纯 Python 结构化提取
  2. _llm_extract()   — LLM 语义提取
  3. _merge_and_save() — 合并结果，写入数据库
"""
import asyncio
import json
import re
from decimal import Decimal
from typing import List, Dict, Optional
from statistics import mean, stdev

from sqlalchemy.orm import Session

from database import (
    Scheme, SchemeItem, PricingLogic, PricingRule, PricingParams,
    Service,
)
from services.baiyan_client import BaiyanClient


class PricingLogicExtractor:
    """定价逻辑提取器"""

    def __init__(self, db: Session, baiyan: BaiyanClient = None):
        self.db = db
        self.baiyan = baiyan

    # ─── 主入口 ──────────────────────────────────────────────

    async def extract_from_historical(
        self,
        scheme_id: int,
        use_llm: bool = True,
    ) -> Dict:
        """
        对单个历史方案执行完整提取管道
        返回: {"logic_id": int, "rules_count": int, "method": str, ...}
        """
        scheme = self.db.query(Scheme).filter(Scheme.id == scheme_id).first()
        if not scheme:
            return {"error": "方案不存在"}

        items = self.db.query(SchemeItem).filter(
            SchemeItem.scheme_id == scheme_id
        ).all()

        if not items:
            return {"error": "方案无服务项"}

        # 步骤1: 规则提取
        rule_result = self._rule_extract(scheme, items)

        # 步骤2: LLM 语义提取（可选）
        llm_result = {}
        if use_llm and self.baiyan:
            try:
                llm_result = await self._llm_extract(scheme, items, rule_result)
            except Exception as e:
                print(f"  LLM提取失败: {e}，使用纯规则结果")
                llm_result = {}

        # 步骤3: 合并保存
        merged = self._merge_and_save(scheme, items, rule_result, llm_result)

        return merged

    async def extract_all_historical(
        self,
        use_llm: bool = True,
    ) -> Dict:
        """
        批量提取所有未处理的历史方案
        返回: {"processed": int, "skipped": int, "errors": int, "details": [...]}
        """
        schemes = self.db.query(Scheme).all()
        processed = 0
        skipped = 0
        errors = 0
        details = []

        for scheme in schemes:
            # 检查是否已提取
            existing = self.db.query(PricingLogic).filter(
                PricingLogic.scheme_id == scheme.id,
                PricingLogic.scheme_type == "historical",
            ).first()

            if existing:
                skipped += 1
                continue

            try:
                result = await self.extract_from_historical(scheme.id, use_llm=use_llm)
                if "error" in result:
                    errors += 1
                    details.append({"scheme_id": scheme.id, "scheme_name": scheme.scheme_name, "error": result["error"]})
                else:
                    processed += 1
                    details.append({"scheme_id": scheme.id, "scheme_name": scheme.scheme_name, "method": result.get("method")})
            except Exception as e:
                errors += 1
                details.append({"scheme_id": scheme.id, "scheme_name": scheme.scheme_name, "error": str(e)})

        return {
            "processed": processed,
            "skipped": skipped,
            "errors": errors,
            "details": details,
        }

    # ─── 步骤1: 规则提取（纯 Python） ─────────────────────────

    def _rule_extract(
        self,
        scheme: Scheme,
        items: List[SchemeItem],
    ) -> Dict:
        """结构化提取 — 不需要 LLM"""

        # 基础统计
        item_count = len(items)
        prices = [it.price for it in items if it.price is not None]
        price_values = [float(p) for p in prices]

        result = {
            "item_count": item_count,
            "priced_items": len(prices),
            "total_price": float(scheme.total_price) if scheme.total_price else None,
        }

        # 价格分布
        if price_values:
            result["price_stats"] = {
                "min": min(price_values),
                "max": max(price_values),
                "avg": round(mean(price_values), 2),
                "median": round(sorted(price_values)[len(price_values) // 2], 2),
            }

        # 频次分布
        freq_counts = {}
        for item in items:
            freq = item.times or "未指定"
            freq_counts[freq] = freq_counts.get(freq, 0) + 1
        result["frequency_distribution"] = freq_counts

        # 从 service_list_json 提取多档位信息
        if scheme.service_list_json:
            try:
                svc_data = json.loads(scheme.service_list_json)
                pricing_data = svc_data.get("pricing_data") or svc_data.get("pricing")
                if pricing_data:
                    tiers_info = pricing_data.get("tiers", {})
                    result["tier_count"] = len(tiers_info)
                    tier_prices = []
                    for tname, tdata in tiers_info.items():
                        tp = tdata.get("target_price") or tdata.get("target_price_range", [0])[0]
                        tier_prices.append(float(tp) if tp else 0)
                    if tier_prices and len(tier_prices) > 1:
                        result["tier_price_range"] = {
                            "min": min(tier_prices),
                            "max": max(tier_prices),
                        }
                        # 档位梯度
                        multipliers = []
                        for i in range(1, len(tier_prices)):
                            if tier_prices[i - 1] > 0:
                                multipliers.append(tier_prices[i] / tier_prices[i - 1])
                        if multipliers:
                            result["tier_multiplier_avg"] = round(mean(multipliers), 2)
            except (json.JSONDecodeError, TypeError):
                pass

        # 取整模式检测
        if price_values:
            int_count = sum(1 for p in price_values if p == int(p))
            half_count = sum(1 for p in price_values if p * 2 == int(p * 2) and p != int(p))
            if int_count > len(price_values) * 0.7:
                result["detected_rounding"] = "round_yuan"
            elif half_count > len(price_values) * 0.3:
                result["detected_rounding"] = "round_half"
            else:
                result["detected_rounding"] = "none"

        # 成本价匹配分析
        matched_costs = []
        for item in items:
            if not item.price:
                continue
            svc = self.db.query(Service).filter(
                Service.name == item.service_name
            ).first()
            if svc and svc.cost_price:
                matched_costs.append({
                    "name": item.service_name,
                    "cost_price": float(svc.cost_price),
                    "historical_price": float(item.price),
                })

        if matched_costs:
            result["cost_price_matches"] = len(matched_costs)
            margins = []
            for mc in matched_costs:
                if mc["cost_price"] > 0:
                    margins.append((mc["historical_price"] - mc["cost_price"]) / mc["cost_price"])
            if margins:
                result["estimated_margin"] = {
                    "avg": round(mean(margins), 4),
                    "min": round(min(margins), 4),
                    "max": round(max(margins), 4),
                }

        return result

    # ─── 步骤2: LLM 语义提取 ──────────────────────────────────

    async def _llm_extract(
        self,
        scheme: Scheme,
        items: List[SchemeItem],
        rule_result: Dict,
    ) -> Dict:
        """LLM 语义提取 — 理解定价方法、设计逻辑、服务角色"""

        if not self.baiyan:
            return {}

        # 构建 prompt
        prompt_template = self._load_prompt_template()
        items_table = self._build_items_table(items)
        rule_analysis = json.dumps(rule_result, ensure_ascii=False, indent=2)

        # 转义注入字符串中的 { } ，避免与 str.format() 的占位符冲突
        def _esc(s: str) -> str:
            return s.replace('{', '{{').replace('}', '}}')

        prompt = prompt_template.format(
            scheme_name=_esc(scheme.scheme_name or "未命名"),
            customer_name=_esc(scheme.customer_name or "未知客户"),
            total_price=_esc(str(scheme.total_price) if scheme.total_price else "未知"),
            source_file=_esc(scheme.source_file or "未知"),
            item_count=len(items),
            service_items_table=_esc(items_table),
            rule_pre_analysis=_esc(rule_analysis),
        )

        # 调用 LLM
        messages = [
            {"role": "system", "content": "你是保险精算分析师。请输出JSON格式，不要有其他内容。"},
            {"role": "user", "content": prompt},
        ]

        response = await self.baiyan.chat_completion(messages, temperature=0.2)
        content = self.baiyan.extract_content(response)

        # 提取 JSON
        try:
            # 尝试从 markdown code block 提取
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            # 尝试直接解析
            return json.loads(content)
        except (json.JSONDecodeError, AttributeError):
            print(f"  LLM 返回非 JSON 内容: {content[:200]}...")
            return {}

    def _load_prompt_template(self) -> str:
        import os
        prompt_path = os.path.join(
            os.path.dirname(__file__), "..", "prompts", "pricing_extraction_prompt.txt"
        )
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def _build_items_table(self, items: List[SchemeItem]) -> str:
        lines = ["| 服务名称 | 次数 | 启动条件 | 报价 |",
                 "|---------|------|---------|------|"]
        for it in items:
            name = it.service_name or ""
            times = it.times or "-"
            cond = (it.condition or "-")[:30]
            price = str(it.price) if it.price else "-"
            lines.append(f"| {name} | {times} | {cond} | {price} |")
        return "\n".join(lines)

    # ─── 步骤3: 合并保存 ──────────────────────────────────────

    def _merge_and_save(
        self,
        scheme: Scheme,
        items: List[SchemeItem],
        rule_result: Dict,
        llm_result: Dict,
    ) -> Dict:
        """合并规则提取和 LLM 提取结果，写入数据库"""

        # 确定定价方法
        pricing_method = llm_result.get("pricing_method", "hybrid")
        confidence = llm_result.get("method_confidence") or (
            0.6 if llm_result else 0.4
        )

        # 构建 extracted_rules_json
        extracted_rules = {
            "pricing_method": pricing_method,
            "estimated_margin": rule_result.get("estimated_margin"),
            "price_stats": rule_result.get("price_stats"),
            "tier_analysis": {
                "tier_count": rule_result.get("tier_count", 1),
                "multiplier_avg": rule_result.get("tier_multiplier_avg"),
                "price_range": rule_result.get("tier_price_range"),
            },
            "detected_rounding": rule_result.get("detected_rounding"),
            "llm_enriched": {
                "tier_design_logic": llm_result.get("tier_design_logic", ""),
                "service_roles": llm_result.get("service_role_mapping", []),
            },
        }

        # 确定 logic_description（优先使用 LLM）
        logic_description = llm_result.get("logic_description", "")
        if not logic_description:
            logic_description = self._generate_description(scheme, rule_result)

        # 创建 PricingLogic
        logic = PricingLogic(
            scheme_id=scheme.id,
            scheme_type="historical",
            pricing_method=pricing_method,
            extracted_rules_json=json.dumps(extracted_rules, ensure_ascii=False),
            logic_description=logic_description,
            confidence_score=round(confidence, 2),
            extracted_by="llm" if llm_result else "rule_only",
        )
        self.db.add(logic)
        self.db.flush()

        # 创建 PricingRules（从 LLM 提取的规则）
        rules_count = 0
        llm_rules = llm_result.get("pricing_rules", [])
        for r in llm_rules:
            rule = PricingRule(
                logic_id=logic.id,
                rule_category=r.get("category", "markup"),
                rule_name=r.get("rule_name", ""),
                rule_expression=r.get("rule_expression", ""),
                rule_params_json=json.dumps(r.get("params", {}), ensure_ascii=False),
                priority=10,
                is_active=1,
            )
            self.db.add(rule)
            rules_count += 1

        # 如果没有 LLM 规则，从 rule_result 生成基础规则
        if rules_count == 0:
            self._create_default_rules(logic.id, rule_result)
            rules_count = sum(1 for _ in [])

        # 创建/更新 PricingParams
        params_suggestion = llm_result.get("pricing_params_suggestion", {})
        if params_suggestion:
            pricing_params = PricingParams(
                name=f"{scheme.scheme_name} - 自动提取",
                scene=self._infer_scene(scheme.scheme_name or ""),
                margin_rate=params_suggestion.get("margin_rate"),
                package_discount=params_suggestion.get("package_discount"),
                rounding_rule=params_suggestion.get("rounding_rule", "round_yuan"),
                channel_coeff=params_suggestion.get("channel_coeff", 1.0),
                source_type="extracted",
                source_scheme_id=scheme.id,
                params_json=json.dumps(params_suggestion, ensure_ascii=False),
            )
            self.db.add(pricing_params)

        self.db.commit()

        return {
            "logic_id": logic.id,
            "method": pricing_method,
            "confidence": confidence,
            "rules_count": rules_count,
            "description": logic_description[:200],
        }

    def _generate_description(self, scheme: Scheme, rule_result: Dict) -> str:
        """当 LLM 不可用时，从规则结果生成描述"""
        method = "成本加成法" if rule_result.get("estimated_margin") else "混合定价法"
        parts = [f"本方案采用{method}。"]

        margin = rule_result.get("estimated_margin")
        if margin:
            parts.append(
                f"估算利润率在{margin['min']:.0%}至{margin['max']:.0%}之间，"
                f"平均约{margin['avg']:.0%}。"
            )

        tier_count = rule_result.get("tier_count", 0)
        if tier_count > 1:
            multiplier = rule_result.get("tier_multiplier_avg", 0)
            parts.append(
                f"共{tier_count}个档位，"
                f"档位间价格递增约{multiplier:.1f}倍。"
            )

        rounding = rule_result.get("detected_rounding")
        if rounding == "round_yuan":
            parts.append("报价取整到整数元。")
        elif rounding == "round_half":
            parts.append("报价取整到0.5元。")

        return "".join(parts)

    def _create_default_rules(
        self,
        logic_id: int,
        rule_result: Dict,
    ):
        """从规则提取结果创建默认规则"""
        margin = rule_result.get("estimated_margin")
        if margin:
            rule = PricingRule(
                logic_id=logic_id,
                rule_category="markup",
                rule_name="历史方案利润率",
                rule_expression=f"cost * (1 + {margin['avg']:.4f})",
                rule_params_json=json.dumps({
                    "avg_margin": margin["avg"],
                    "min_margin": margin["min"],
                    "max_margin": margin["max"],
                }, ensure_ascii=False),
                priority=5,
                is_active=1,
            )
            self.db.add(rule)

        rounding = rule_result.get("detected_rounding")
        if rounding:
            rule = PricingRule(
                logic_id=logic_id,
                rule_category="rounding",
                rule_name=f"取整规则: {rounding}",
                rule_expression=f"apply_rounding(price, '{rounding}')",
                rule_params_json=json.dumps({"method": rounding}, ensure_ascii=False),
                priority=3,
                is_active=1,
            )
            self.db.add(rule)

    def _infer_scene(self, scheme_name: str) -> str:
        """从方案名称推断场景"""
        if "随车" in scheme_name:
            return "随车健管"
        if "银行" in scheme_name or "城商行" in scheme_name:
            return "银行渠道"
        if "职工" in scheme_name or "防癌" in scheme_name:
            return "职工福利"
        return "通用"
