"""
定价引擎 API 路由
"""
import json
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from database import get_db, PricingLogic, PricingRule, PricingParams, GeneratedScheme, Scheme
from models.schemas import ApiResponse
from services.pricing_engine import PricingEngine
from services.pricing_knowledge import PricingKnowledgeBase
from services.pricing_extractor import PricingLogicExtractor

router = APIRouter()


# ─── 定价逻辑 ──────────────────────────────────────────────

@router.get("/logics", response_model=ApiResponse)
async def list_pricing_logics(
    method: str = Query(None, description="定价方法: cost_plus/market_benchmark/hybrid/tiered"),
    scheme_type: str = Query(None, description="方案类型: historical/generated"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """获取定价逻辑列表"""
    kbase = PricingKnowledgeBase(db)
    logics = kbase.list_logics(method=method, limit=limit)

    # 按 scheme_type 过滤
    if scheme_type:
        logics = [l for l in logics if l.scheme_type == scheme_type]

    return ApiResponse(data=[
        {
            "id": l.id,
            "scheme_id": l.scheme_id,
            "scheme_type": l.scheme_type,
            "pricing_method": l.pricing_method,
            "logic_description": (l.logic_description or "")[:200],
            "confidence_score": float(l.confidence_score) if l.confidence_score else None,
            "extracted_by": l.extracted_by,
            "create_time": str(l.create_time) if l.create_time else None,
        }
        for l in logics
    ])


@router.get("/logics/{logic_id}", response_model=ApiResponse)
async def get_pricing_logic(
    logic_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """获取单个定价逻辑详情（含关联规则）"""
    logic = db.query(PricingLogic).filter(PricingLogic.id == logic_id).first()
    if not logic:
        raise HTTPException(status_code=404, detail="定价逻辑不存在")

    rules = db.query(PricingRule).filter(
        PricingRule.logic_id == logic_id,
        PricingRule.is_active == 1,
    ).order_by(PricingRule.priority.desc()).all()

    return ApiResponse(data={
        "id": logic.id,
        "scheme_id": logic.scheme_id,
        "scheme_type": logic.scheme_type,
        "pricing_method": logic.pricing_method,
        "logic_description": logic.logic_description,
        "extracted_rules": json.loads(logic.extracted_rules_json) if logic.extracted_rules_json else {},
        "diff_vs_engine": logic.diff_vs_engine,
        "diff_vs_previous": logic.diff_vs_previous,
        "confidence_score": float(logic.confidence_score) if logic.confidence_score else None,
        "extracted_by": logic.extracted_by,
        "rules": [
            {
                "id": r.id,
                "category": r.rule_category,
                "name": r.rule_name,
                "expression": r.rule_expression,
                "params": json.loads(r.rule_params_json) if r.rule_params_json else {},
                "priority": r.priority,
            }
            for r in rules
        ],
    })


# ─── 定价规则 ──────────────────────────────────────────────

@router.get("/rules", response_model=ApiResponse)
async def list_pricing_rules(
    category: str = Query(None, description="规则类别: markup/tiering/rounding/selection/discount"),
    db: Session = Depends(get_db),
):
    """获取定价规则列表"""
    kbase = PricingKnowledgeBase(db)
    if category:
        rules = kbase.find_rules_by_category(category)
    else:
        rules = db.query(PricingRule).filter(PricingRule.is_active == 1).all()

    return ApiResponse(data=[
        {
            "id": r.id,
            "logic_id": r.logic_id,
            "category": r.rule_category,
            "name": r.rule_name,
            "expression": r.rule_expression,
            "params": json.loads(r.rule_params_json) if r.rule_params_json else {},
            "priority": r.priority,
        }
        for r in rules
    ])


# ─── 定价参数 ──────────────────────────────────────────────

@router.get("/params", response_model=ApiResponse)
async def list_pricing_params(
    scene: str = Query(None, description="场景过滤"),
    channel: str = Query(None, description="渠道过滤"),
    db: Session = Depends(get_db),
):
    """获取定价参数列表"""
    kbase = PricingKnowledgeBase(db)
    params = kbase.find_params(scene=scene, channel=channel)

    return ApiResponse(data=[
        {
            "id": p.id,
            "name": p.name,
            "scene": p.scene,
            "volume_min": p.volume_min,
            "volume_max": p.volume_max,
            "channel": p.channel,
            "margin_rate": float(p.margin_rate) if p.margin_rate else None,
            "channel_coeff": float(p.channel_coeff) if p.channel_coeff else None,
            "package_discount": float(p.package_discount) if p.package_discount else None,
            "rounding_rule": p.rounding_rule,
            "source_type": p.source_type,
        }
        for p in params
    ])


# ─── 定价统计 ──────────────────────────────────────────────

@router.get("/stats", response_model=ApiResponse)
async def get_pricing_stats(db: Session = Depends(get_db)):
    """定价统计分析（利润率分布、场景概览）"""
    kbase = PricingKnowledgeBase(db)

    markup_stats = kbase.get_markup_stats()
    scene_overview = kbase.get_scene_pricing_overview()

    return ApiResponse(data={
        "markup_by_method": markup_stats,
        "scene_overview": scene_overview,
    })


# ─── 相似方案检索 ──────────────────────────────────────────

@router.get("/similar/{scheme_id}", response_model=ApiResponse)
async def find_similar_schemes(
    scheme_id: int = Path(..., ge=1),
    top_k: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db),
):
    """查找与指定方案定价相似的历史方案"""
    scheme = db.query(GeneratedScheme).filter(GeneratedScheme.id == scheme_id).first()
    if not scheme:
        scheme = db.query(Scheme).filter(Scheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="方案不存在")

    kbase = PricingKnowledgeBase(db)
    similar = kbase.find_similar_schemes(
        scene=getattr(scheme, 'scene', None),
        top_k=top_k,
    )

    return ApiResponse(data=similar)


# ─── 定价对比 ──────────────────────────────────────────────

@router.get("/compare", response_model=ApiResponse)
async def compare_pricing(
    scheme_a: int = Query(..., description="方案A ID"),
    scheme_b: int = Query(..., description="方案B ID"),
    db: Session = Depends(get_db),
):
    """两个方案的定价差异对比"""
    kbase = PricingKnowledgeBase(db)
    result = kbase.compare_pricing(scheme_a, scheme_b)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return ApiResponse(data=result)


# ─── 定价提取 ──────────────────────────────────────────────

@router.post("/extract/{scheme_id}", response_model=ApiResponse)
async def extract_pricing_logic(
    scheme_id: int = Path(..., ge=1),
    use_llm: bool = Query(True, description="是否使用LLM语义提取"),
    db: Session = Depends(get_db),
):
    """对历史方案执行定价逻辑提取"""
    from services.baiyan_client import get_baiyan_client
    baiyan = get_baiyan_client()
    extractor = PricingLogicExtractor(db, baiyan)
    result = await extractor.extract_from_historical(scheme_id, use_llm=use_llm)

    return ApiResponse(data=result)


@router.post("/extract-all", response_model=ApiResponse)
async def extract_all_pricing_logics(
    use_llm: bool = Query(True),
    db: Session = Depends(get_db),
):
    """批量提取所有未处理的历史方案定价逻辑"""
    from services.baiyan_client import get_baiyan_client
    baiyan = get_baiyan_client()
    extractor = PricingLogicExtractor(db, baiyan)
    result = await extractor.extract_all_historical(use_llm=use_llm)

    return ApiResponse(data=result)


# ─── 方案定价详情 ──────────────────────────────────────────

@router.get("/scheme/{scheme_id}", response_model=ApiResponse)
async def get_scheme_pricing(
    scheme_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """获取方案的完整定价信息（引擎价 vs LLM价 vs 最终价）"""
    scheme = db.query(GeneratedScheme).filter(GeneratedScheme.id == scheme_id).first()

    if not scheme:
        # 也查历史方案
        scheme = db.query(Scheme).filter(Scheme.id == scheme_id).first()

    if not scheme:
        raise HTTPException(status_code=404, detail="方案不存在")

    if isinstance(scheme, GeneratedScheme):
        # 计算引擎价 vs LLM价偏差
        deviation = None
        if scheme.engine_total_quote and scheme.llm_total_quote and scheme.engine_total_quote > 0:
            deviation = float(
                abs(scheme.llm_total_quote - scheme.engine_total_quote) / scheme.engine_total_quote
            )

        logic_data = None
        if scheme.pricing_logic_id:
            logic = db.query(PricingLogic).filter(PricingLogic.id == scheme.pricing_logic_id).first()
            if logic:
                logic_data = {
                    "method": logic.pricing_method,
                    "description": logic.logic_description,
                    "confidence": float(logic.confidence_score) if logic.confidence_score else None,
                }

        return ApiResponse(data={
            "type": "generated",
            "id": scheme.id,
            "name": scheme.scheme_name,
            "pricing_method": scheme.pricing_method,
            "engine_total_cost": float(scheme.engine_total_cost) if scheme.engine_total_cost else None,
            "engine_total_quote": float(scheme.engine_total_quote) if scheme.engine_total_quote else None,
            "llm_total_cost": float(scheme.llm_total_cost) if scheme.llm_total_cost else None,
            "llm_total_quote": float(scheme.llm_total_quote) if scheme.llm_total_quote else None,
            "final_total_cost": float(scheme.final_total_cost) if scheme.final_total_cost else None,
            "final_total_quote": float(scheme.final_total_quote) if scheme.final_total_quote else None,
            "deviation": deviation,
            "pricing_logic": logic_data,
        })

    # 历史方案
    engine = PricingEngine(db)
    margin_info = engine.reverse_engineer_margin(scheme_id)

    return ApiResponse(data={
        "type": "historical",
        "id": scheme.id,
        "name": scheme.scheme_name,
        "customer": scheme.customer_name,
        "total_price": float(scheme.total_price) if scheme.total_price else None,
        "reverse_engineered": margin_info,
    })
