"""
定价规则引擎 — 纯 Python 计算，不依赖 LLM

核心公式:
  预期成本 = cost_price × usage_rate × frequency
  单服务报价 = 预期成本 × (1 + margin_rate) × channel_coeff
  方案总价 = Σ 单服务报价 × package_discount → apply_rounding

使用示例:
    engine = PricingEngine(db)
    params = PricingParams(
        margin_rate=Decimal("0.15"),
        volume=50000,
        ...
    )
    result = engine.calculate_all_tiers(tier_configs, params)
"""
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP, ROUND_UP
from typing import List, Optional, Dict, Tuple
from sqlalchemy.orm import Session

from database import Service, Scheme, SchemeItem


@dataclass
class ServicePricingInput:
    """单服务定价输入"""
    service_id: int
    name: str
    cost_price: Decimal          # 从 Service 表获取
    usage_rate: Decimal           # 根据规模选择的发生率
    frequency: int = 1            # 服务次数
    pricing_category: str = "per_use"


@dataclass
class PricingParams:
    """定价参数"""
    margin_rate: Decimal = Decimal("0.15")       # 利润率
    channel_coeff: Decimal = Decimal("1.0")      # 渠道系数
    package_discount: Decimal = Decimal("0.90")  # 打包折扣
    rounding_rule: str = "round_yuan"            # 取整: round_yuan/round_half/ceil/none
    volume: int = 10000                           # 保单规模
    usage_rate_column: str = "small"              # "small" | "large"


@dataclass
class PricedService:
    """单服务定价结果"""
    service_id: int
    name: str
    cost_price: Decimal
    usage_rate: Decimal
    frequency: int
    expected_cost: Decimal       # = cost_price × usage_rate × frequency
    quoted_price: Decimal        # = expected_cost × (1 + margin) × channel_coeff
    margin_amount: Decimal       # = quoted_price - expected_cost
    margin_rate: Decimal


@dataclass
class PricedTier:
    """单档位定价结果"""
    tier_name: str
    target_price_range: Tuple[float, float] = (0, 0)
    services: List[PricedService] = field(default_factory=list)
    total_cost: Decimal = Decimal("0")
    total_quote: Decimal = Decimal("0")
    final_price: Decimal = Decimal("0")


class PricingEngine:
    """定价规则引擎"""

    def __init__(self, db: Session):
        self.db = db

    # ─── 核心计算 ─────────────────────────────────────────────

    def calculate_single_service(
        self,
        service: ServicePricingInput,
        params: PricingParams,
    ) -> PricedService:
        """
        单服务定价:
          expected_cost = cost_price × usage_rate × frequency
          quoted_price  = expected_cost × (1 + margin_rate) × channel_coeff
        """
        expected_cost = (service.cost_price *
                         service.usage_rate *
                         Decimal(str(service.frequency)))

        quoted_price = (expected_cost *
                        (Decimal("1") + params.margin_rate) *
                        params.channel_coeff)

        margin_amount = quoted_price - expected_cost

        return PricedService(
            service_id=service.service_id,
            name=service.name,
            cost_price=service.cost_price,
            usage_rate=service.usage_rate,
            frequency=service.frequency,
            expected_cost=expected_cost,
            quoted_price=quoted_price,
            margin_amount=margin_amount,
            margin_rate=params.margin_rate,
        )

    def calculate_tier(
        self,
        tier_name: str,
        services: List[ServicePricingInput],
        params: PricingParams,
        target_range: Tuple[float, float] = (0, 0),
    ) -> PricedTier:
        """
        单档位定价:
          1. 逐服务 calculate_single_service
          2. total_cost = Σ expected_cost
          3. total_quote = Σ quoted_price × package_discount
          4. final_price = apply_rounding(total_quote)
        """
        priced = [self.calculate_single_service(s, params) for s in services]

        total_cost = sum((p.expected_cost for p in priced), Decimal("0"))
        raw_total = sum((p.quoted_price for p in priced), Decimal("0"))
        total_quote = raw_total * params.package_discount
        final_price = self.apply_rounding(total_quote, params.rounding_rule)

        return PricedTier(
            tier_name=tier_name,
            target_price_range=target_range,
            services=priced,
            total_cost=total_cost,
            total_quote=total_quote,
            final_price=final_price,
        )

    def calculate_all_tiers(
        self,
        tier_configs: List[Dict],
        params: PricingParams,
    ) -> List[PricedTier]:
        """
        多档位批量计算

        tier_configs 格式:
        [
            {
                "name": "基础档",
                "target_range": (25, 30),
                "services": [ServicePricingInput, ...]
            },
            ...
        ]
        """
        results = []
        for cfg in tier_configs:
            tier = self.calculate_tier(
                tier_name=cfg["name"],
                services=cfg["services"],
                params=params,
                target_range=cfg.get("target_range", (0, 0)),
            )
            results.append(tier)
        return results

    # ─── 取整规则 ─────────────────────────────────────────────

    def apply_rounding(self, value: Decimal, rule: str) -> Decimal:
        """取整处理"""
        if rule == "round_yuan":
            return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        elif rule == "round_half":
            # 向上取整到 0.5
            doubled = value * Decimal("2")
            rounded = doubled.quantize(Decimal("1"), rounding=ROUND_UP)
            return rounded / Decimal("2")
        elif rule == "ceil":
            return value.quantize(Decimal("1"), rounding=ROUND_UP)
        elif rule == "floor":
            import decimal
            return value.quantize(Decimal("1"), rounding=decimal.ROUND_DOWN)
        else:
            return value

    # ─── 数据库查询辅助 ───────────────────────────────────────

    def load_service_pricing_input(
        self,
        service_name: str,
        params: PricingParams,
    ) -> Optional[ServicePricingInput]:
        """
        从 Service 表加载单个服务的定价输入
        自动选择正确的发生率列
        """
        svc = self.db.query(Service).filter(
            Service.name == service_name
        ).first()

        if not svc or svc.cost_price is None:
            return None

        usage_rate = (svc.usage_rate_small
                      if params.usage_rate_column == "small"
                      else svc.usage_rate_large)
        if usage_rate is None:
            usage_rate = Decimal("1.0")  # 默认 100% 发生率

        return ServicePricingInput(
            service_id=svc.id,
            name=svc.name,
            cost_price=svc.cost_price,
            usage_rate=usage_rate,
            frequency=1,
            pricing_category=svc.pricing_category or "per_use",
        )

    def load_services_for_names(
        self,
        names: List[str],
        params: PricingParams,
    ) -> List[ServicePricingInput]:
        """批量加载服务定价输入"""
        result = []
        for name in names:
            inp = self.load_service_pricing_input(name, params)
            if inp:
                result.append(inp)
        return result

    # ─── 定价参数工厂方法 ─────────────────────────────────────

    def create_params_from_volume(
        self,
        volume: int,
        scene: str = "",
        channel: str = "",
    ) -> PricingParams:
        """
        根据规模和场景自动创建定价参数
        """
        params = PricingParams(volume=volume)

        # 根据规模选择发生率列
        if volume < 50000:
            params.usage_rate_column = "small"
        else:
            params.usage_rate_column = "large"

        # 根据渠道调整系数（可后续从 pricing_params 表读取）
        if "银行" in channel:
            params.channel_coeff = Decimal("1.05")
        elif "随车" in channel or "随车" in scene:
            params.channel_coeff = Decimal("0.95")

        return params

    # ─── 逐服务利润率（差异化利润率） ──────────────────────────

    def get_service_margin(
        self,
        pricing_category: str,
        base_margin: Decimal,
    ) -> Decimal:
        """
        根据定价类别返回差异化利润率:
          - 高频刚需 (per_year): 低利润率 10%
          - 一次性事件 (per_event): 中等利润率 15%
          - 低频高价值 (per_use): 较高利润率 20%
          - 折扣型 (discount): 零利润率
        """
        adjustments = {
            "per_year": Decimal("-0.05"),
            "per_event": Decimal("0"),
            "per_use": Decimal("0.05"),
            "discount": Decimal("-0.15"),
        }
        adj = adjustments.get(pricing_category, Decimal("0"))
        return max(base_margin + adj, Decimal("0"))

    # ─── 偏差校验 ─────────────────────────────────────────────

    def validate_deviation(
        self,
        engine_price: Decimal,
        llm_price: Decimal,
        max_deviation: Decimal = Decimal("0.20"),
    ) -> Dict:
        """
        校验 LLM 报价与引擎价的偏差
        返回: {"pass": bool, "deviation": float, "severity": "ok"|"warn"|"error"}
        """
        if engine_price == 0:
            return {"pass": True, "deviation": 0, "severity": "ok"}
        deviation = abs(llm_price - engine_price) / engine_price
        if deviation <= max_deviation:
            return {"pass": True, "deviation": float(deviation), "severity": "ok"}
        elif deviation <= max_deviation * 2:
            return {"pass": True, "deviation": float(deviation), "severity": "warn"}
        else:
            return {"pass": False, "deviation": float(deviation), "severity": "error"}

    # ─── 从历史方案反算利润率 ──────────────────────────────────

    def reverse_engineer_margin(
        self,
        scheme_id: int,
        volume: int = 50000,
    ) -> Dict:
        """
        从历史方案反算利润率。
        给定一个 Scheme 的 service_items 和 total_price，
        通过匹配 Service 表的 cost_price 反算利润率。

        返回: {"estimated_margin": 0.15, "per_service": [...], "confidence": 0.8}
        """
        scheme = self.db.query(Scheme).filter(Scheme.id == scheme_id).first()
        if not scheme:
            return {"error": "方案不存在"}

        import json
        items = self.db.query(SchemeItem).filter(
            SchemeItem.scheme_id == scheme_id
        ).all()

        if not items:
            return {"error": "方案无服务项"}

        per_service = []
        margin_sum = Decimal("0")
        margin_count = 0

        for item in items:
            svc = self.db.query(Service).filter(
                Service.name == item.service_name
            ).first()

            if svc and svc.cost_price and item.price:
                usage_rate = svc.usage_rate_small if volume < 50000 else svc.usage_rate_large
                if usage_rate is None:
                    usage_rate = Decimal("1")

                expected_cost = svc.cost_price * usage_rate
                if expected_cost > 0:
                    implied_margin = (Decimal(str(item.price)) - expected_cost) / expected_cost
                    margin_sum += implied_margin
                    margin_count += 1
                    per_service.append({
                        "name": item.service_name,
                        "cost_price": float(svc.cost_price),
                        "usage_rate": float(usage_rate),
                        "expected_cost": float(expected_cost),
                        "historical_price": float(item.price),
                        "implied_margin": float(implied_margin),
                    })

        if margin_count == 0:
            return {"error": "无可反算的服务项（缺少成本价数据）"}

        avg_margin = margin_sum / Decimal(str(margin_count))
        return {
            "estimated_margin": float(avg_margin),
            "per_service": per_service,
            "confidence": min(1.0, margin_count / len(items)),
            "method": "reverse_engineered_from_cost",
        }
