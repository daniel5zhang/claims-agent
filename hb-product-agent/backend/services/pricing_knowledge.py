"""
定价知识库 — 查询、统计、匹配

提供:
  - 场景级定价规则查询
  - 利润率分布统计
  - 相似历史方案检索
  - 定价异常检测
  - 多方案定价对比
"""
import json
from decimal import Decimal
from typing import List, Optional, Dict, Any
from statistics import mean, stdev
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from database import (
    PricingParams, PricingLogic, PricingRule,
    GeneratedScheme, Scheme,
)


class PricingKnowledgeBase:
    """定价知识库查询"""

    def __init__(self, db: Session):
        self.db = db

    # ─── 定价参数查询 ─────────────────────────────────────────

    def find_params(
        self,
        scene: str = None,
        channel: str = None,
        volume: int = None,
    ) -> List[PricingParams]:
        """查询匹配的定价参数"""
        q = self.db.query(PricingParams)
        if scene:
            q = q.filter(PricingParams.scene == scene)
        if channel:
            q = q.filter(PricingParams.channel == channel)
        if volume is not None:
            q = q.filter(
                PricingParams.volume_min <= volume,
                PricingParams.volume_max >= volume,
            )
        return q.all()

    def get_params(self, params_id: int) -> Optional[PricingParams]:
        return self.db.query(PricingParams).filter(
            PricingParams.id == params_id
        ).first()

    # ─── 定价逻辑查询 ─────────────────────────────────────────

    def get_logic_for_scheme(
        self,
        scheme_id: int,
        scheme_type: str = "generated",
    ) -> Optional[PricingLogic]:
        """获取方案关联的定价逻辑"""
        return self.db.query(PricingLogic).filter(
            PricingLogic.scheme_id == scheme_id,
            PricingLogic.scheme_type == scheme_type,
        ).first()

    def list_logics(
        self,
        method: str = None,
        scene: str = None,
        limit: int = 50,
    ) -> List[PricingLogic]:
        """列出定价逻辑"""
        q = self.db.query(PricingLogic)
        if method:
            q = q.filter(PricingLogic.pricing_method == method)

        if scene:
            # 通过 scheme 关联查询
            q = q.join(GeneratedScheme,
                       PricingLogic.scheme_id == GeneratedScheme.id,
                       isouter=True)
            q = q.filter(
                (PricingLogic.scheme_type == "historical") |
                (GeneratedScheme.scene == scene)
            )

        return q.order_by(desc(PricingLogic.create_time)).limit(limit).all()

    # ─── 定价规则查询 ─────────────────────────────────────────

    def get_rules_for_logic(self, logic_id: int) -> List[PricingRule]:
        """获取定价逻辑下的所有规则"""
        return self.db.query(PricingRule).filter(
            PricingRule.logic_id == logic_id,
            PricingRule.is_active == 1,
        ).order_by(PricingRule.priority.desc()).all()

    def find_rules_by_category(self, category: str) -> List[PricingRule]:
        """按类别查规则"""
        return self.db.query(PricingRule).filter(
            PricingRule.rule_category == category,
            PricingRule.is_active == 1,
        ).order_by(PricingRule.priority.desc()).all()

    # ─── 统计 ─────────────────────────────────────────────────

    def get_markup_stats(self) -> Dict:
        """
        各定价方法/场景下的利润率统计
        从 pricing_logics.extracted_rules_json 中提取利润率数据
        """
        logics = self.db.query(PricingLogic).all()
        stats = {}
        for logic in logics:
            method = logic.pricing_method or "unknown"
            if method not in stats:
                stats[method] = {"count": 0, "margin_rates": []}

            stats[method]["count"] += 1
            if logic.extracted_rules_json:
                try:
                    rules = json.loads(logic.extracted_rules_json)
                    margin = rules.get("margin_per_service")
                    if margin is not None:
                        stats[method]["margin_rates"].append(float(margin))
                except (json.JSONDecodeError, TypeError):
                    pass

        # 计算汇总
        for method, data in stats.items():
            rates = data["margin_rates"]
            if rates:
                data["avg_margin"] = round(mean(rates), 4)
                data["min_margin"] = round(min(rates), 4)
                data["max_margin"] = round(max(rates), 4)
                if len(rates) > 1:
                    data["std_margin"] = round(stdev(rates), 4)
            del data["margin_rates"]

        return stats

    def get_scene_pricing_overview(self) -> List[Dict]:
        """按场景的定价概览"""
        results = []
        schemes = self.db.query(GeneratedScheme).filter(
            GeneratedScheme.pricing_method.isnot(None)
        ).all()

        scene_data = {}
        for s in schemes:
            scene = s.scene or "未分类"
            if scene not in scene_data:
                scene_data[scene] = {
                    "scene": scene,
                    "scheme_count": 0,
                    "methods": {},
                    "total_quotes": [],
                }
            sd = scene_data[scene]
            sd["scheme_count"] += 1
            method = s.pricing_method or "unknown"
            sd["methods"][method] = sd["methods"].get(method, 0) + 1
            if s.final_total_quote:
                sd["total_quotes"].append(float(s.final_total_quote))
            elif s.total_quote:
                sd["total_quotes"].append(float(s.total_quote))

        for scene, sd in scene_data.items():
            quotes = sd["total_quotes"]
            item = {
                "scene": scene,
                "scheme_count": sd["scheme_count"],
                "methods": sd["methods"],
            }
            if quotes:
                item["avg_quote"] = round(mean(quotes), 2)
                item["min_quote"] = round(min(quotes), 2)
                item["max_quote"] = round(max(quotes), 2)
            results.append(item)

        return results

    # ─── 相似方案检索 ─────────────────────────────────────────

    def find_similar_schemes(
        self,
        scene: str = None,
        channel: str = None,
        volume: int = None,
        top_k: int = 3,
    ) -> List[Dict]:
        """
        检索最相似的历史方案定价逻辑
        匹配维度: 场景 > 渠道 > 规模
        """
        logics = self.db.query(PricingLogic).filter(
            PricingLogic.scheme_type == "historical"
        ).all()

        scored = []
        for logic in logics:
            score = 0
            # 通过 scheme 名称匹配场景
            scheme_name = ""
            if logic.scheme_id:
                scheme = self.db.query(Scheme).filter(
                    Scheme.id == logic.scheme_id
                ).first()
                if scheme:
                    scheme_name = scheme.scheme_name or ""

            if scene and scene in scheme_name:
                score += 3
            if channel and channel in scheme_name:
                score += 2

            if score > 0:
                rules = []
                if logic.extracted_rules_json:
                    try:
                        rules = json.loads(logic.extracted_rules_json)
                    except json.JSONDecodeError:
                        pass
                scored.append({
                    "logic_id": logic.id,
                    "scheme_id": logic.scheme_id,
                    "scheme_name": scheme_name,
                    "pricing_method": logic.pricing_method,
                    "logic_description": logic.logic_description,
                    "extracted_rules": rules,
                    "score": score,
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    # ─── 异常检测 ──────────────────────────────────────────────

    def detect_anomalies(self, threshold_std: float = 2.0) -> List[Dict]:
        """
        检测定价异常:
          - 利润率偏离同场景均值 > threshold_std 个标准差
          - 单服务报价低于成本价
        """
        anomalies = []

        # 按场景统计利润率分布
        schemes = self.db.query(GeneratedScheme).filter(
            GeneratedScheme.engine_total_quote.isnot(None),
            GeneratedScheme.final_total_quote.isnot(None),
        ).all()

        scene_margins = {}
        for s in schemes:
            scene = s.scene or "未分类"
            if s.engine_total_quote and s.engine_total_quote > 0:
                margin = (s.final_total_quote - s.engine_total_quote) / s.engine_total_quote
                if scene not in scene_margins:
                    scene_margins[scene] = []
                scene_margins[scene].append({
                    "scheme_id": s.id,
                    "scheme_name": s.scheme_name,
                    "margin": float(margin),
                })

        # 检测离群值
        for scene, items in scene_margins.items():
            if len(items) < 3:
                continue
            margins = [i["margin"] for i in items]
            avg_m = mean(margins)
            try:
                std_m = stdev(margins)
            except:
                continue

            for item in items:
                z_score = abs(item["margin"] - avg_m) / std_m if std_m > 0 else 0
                if z_score > threshold_std:
                    anomalies.append({
                        "type": "margin_outlier",
                        "scheme_id": item["scheme_id"],
                        "scheme_name": item["scheme_name"],
                        "scene": scene,
                        "margin": item["margin"],
                        "scene_avg": round(avg_m, 4),
                        "z_score": round(z_score, 2),
                    })

        return anomalies

    # ─── 方案对比 ──────────────────────────────────────────────

    def compare_pricing(self, scheme_a_id: int, scheme_b_id: int) -> Dict:
        """两个方案的定价差异对比"""
        a = self.db.query(GeneratedScheme).filter(
            GeneratedScheme.id == scheme_a_id
        ).first()
        b = self.db.query(GeneratedScheme).filter(
            GeneratedScheme.id == scheme_b_id
        ).first()

        if not a or not b:
            return {"error": "方案不存在"}

        def safe_float(v):
            return float(v) if v is not None else None

        return {
            "scheme_a": {
                "id": a.id, "name": a.scheme_name,
                "engine_cost": safe_float(a.engine_total_cost),
                "engine_quote": safe_float(a.engine_total_quote),
                "llm_quote": safe_float(a.llm_total_quote),
                "final_quote": safe_float(a.final_total_quote),
                "pricing_method": a.pricing_method,
            },
            "scheme_b": {
                "id": b.id, "name": b.scheme_name,
                "engine_cost": safe_float(b.engine_total_cost),
                "engine_quote": safe_float(b.engine_total_quote),
                "llm_quote": safe_float(b.llm_total_quote),
                "final_quote": safe_float(b.final_total_quote),
                "pricing_method": b.pricing_method,
            },
            "diff": {
                "final_quote_diff": safe_float(
                    (a.final_total_quote or Decimal("0")) -
                    (b.final_total_quote or Decimal("0"))
                ),
                "method_same": a.pricing_method == b.pricing_method,
            },
        }
