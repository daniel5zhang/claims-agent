"""
方案生成引擎
- 基于需求和服务素材生成方案
- 参考历史方案进行定价和组合推荐
"""
import json
from typing import List, Dict, Any, Optional
from decimal import Decimal
from sqlalchemy.orm import Session

from database import Service, Scheme, SchemeItem, GeneratedScheme


def generate_scheme_from_needs(
    db: Session,
    needs: Dict[str, Any],
    conversation_id: int,
) -> Optional[GeneratedScheme]:
    """
    基于已提取的需求生成初始方案。
    实际逻辑由 Agent 在 agent_service.py 中完成，
    此模块提供辅助函数：素材检索、历史方案参考。
    """
    preferences = needs.get("service_preferences", [])
    budget_str = needs.get("budget_range", "")

    # 根据偏好从素材库检索服务
    matched_services = []
    for pref in preferences:
        svcs = search_services(db, pref)
        matched_services.extend(svcs)

    # 去重
    seen = set()
    unique_services = []
    for s in matched_services:
        if s.name not in seen:
            seen.add(s.name)
            unique_services.append(s)

    # 构建方案服务列表
    services_list = []
    total_cost = Decimal("0")
    for svc in unique_services[:8]:  # 最多8项服务
        cost = svc.cost_price or Decimal("0")
        # 报价 = 成本 * 1.3（简单示例，实际应由模型决定）
        quote = cost * Decimal("1.3") if cost else Decimal("0")
        services_list.append({
            "name": svc.name,
            "times": svc.times or "按需求",
            "condition": svc.condition or "",
            "cost": float(cost),
            "price": float(quote.quantize(Decimal("0.01"))),
            "remark": svc.description or "",
        })
        total_cost += cost

    total_quote = total_cost * Decimal("1.3") if total_cost else Decimal("0")

    scheme = GeneratedScheme(
        conversation_id=conversation_id,
        scheme_name=f"{needs.get('scene', '定制')}健管服务方案",
        service_list_json=json.dumps(services_list, ensure_ascii=False),
        total_cost=total_cost,
        total_quote=total_quote.quantize(Decimal("0.01")),
        status="draft",
    )
    db.add(scheme)
    db.commit()
    db.refresh(scheme)
    return scheme


def search_services(db: Session, keyword: str, limit: int = 10) -> List[Service]:
    """根据关键词搜索服务素材"""
    return db.query(Service).filter(
        Service.name.contains(keyword)
        | Service.description.contains(keyword)
        | Service.category.contains(keyword)
    ).limit(limit).all()


def get_similar_schemes(db: Session, scene: str, limit: int = 3) -> List[Scheme]:
    """获取相似场景的历史方案作为参考"""
    return db.query(Scheme).filter(
        Scheme.scheme_name.contains(scene)
        | Scheme.customer_name.contains(scene)
    ).limit(limit).all()


def build_services_context(db: Session) -> str:
    """构建服务素材库上下文，用于注入 Prompt"""
    services = db.query(Service).all()
    lines = ["# 可用服务素材库"]
    for svc in services:
        lines.append(
            f"- {svc.name}（{svc.category or '未分类'}）:\n"
            f"  说明: {svc.description or '无'}\n"
            f"  次数: {svc.times or '未指定'}\n"
            f"  启动条件: {svc.condition or '无'}\n"
            f"  成本价: {svc.cost_price or '未定价'}元"
        )
    return "\n".join(lines)
