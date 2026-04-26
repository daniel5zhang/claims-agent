"""
方案接口路由
"""
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db, GeneratedScheme, Conversation
from models.schemas import (
    SchemeConfirmRequest,
    SchemeAdjustRequest,
    GeneratedSchemeOut,
    SchemeItemOut,
    ApiResponse,
)
from services.agent_service import get_agent_service

router = APIRouter()


def _get_user_id(request: Request) -> str:
    """从请求状态中获取 user_id"""
    return getattr(request.state, "user_id", "")


def _verify_scheme_owner(db: Session, scheme_id: int, user_id: str) -> GeneratedScheme:
    """校验方案是否属于当前用户，返回方案对象"""
    scheme = db.query(GeneratedScheme).filter(GeneratedScheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="方案不存在")
    # 通过 conversation_id 关联校验用户归属
    if user_id:
        conv = db.query(Conversation).filter(Conversation.id == scheme.conversation_id).first()
        if conv and conv.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权访问此方案")
    return scheme


@router.get("/{scheme_id}", response_model=ApiResponse)
async def get_scheme(scheme_id: int, request: Request, db: Session = Depends(get_db)):
    """获取方案详情"""
    user_id = _get_user_id(request)
    scheme = _verify_scheme_owner(db, scheme_id, user_id)
    return ApiResponse(data=_scheme_to_dict(scheme, db))


@router.post("/{scheme_id}/update", response_model=ApiResponse)
async def update_scheme(
    scheme_id: int,
    req: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    """更新方案内容（用于切换选中的方案）"""
    user_id = _get_user_id(request)
    scheme = _verify_scheme_owner(db, scheme_id, user_id)

    # 更新方案字段
    if req.get("scheme_name"):
        scheme.scheme_name = req["scheme_name"]
    if req.get("scene") is not None:
        scheme.scene = req["scene"]
    if req.get("target_group") is not None:
        scheme.target_group = req["target_group"]
    if req.get("service_list"):
        # 读取现有的完整 JSON，只更新 services
        try:
            raw_data = json.loads(scheme.service_list_json or "{}")
            if not isinstance(raw_data, dict):
                raw_data = {"services": raw_data}
        except Exception:
            raw_data = {}
        raw_data["services"] = req["service_list"]
        scheme.service_list_json = json.dumps(raw_data, ensure_ascii=False)
    if req.get("total_cost") is not None:
        from decimal import Decimal
        scheme.total_cost = Decimal(str(req["total_cost"]))
    if req.get("total_quote") is not None:
        from decimal import Decimal
        scheme.total_quote = Decimal(str(req["total_quote"]))

    db.commit()
    return ApiResponse(data=_scheme_to_dict(scheme, db))


@router.post("/{scheme_id}/confirm", response_model=ApiResponse)
async def confirm_scheme(
    scheme_id: int, req: SchemeConfirmRequest, request: Request, db: Session = Depends(get_db)
):
    """确认/取消确认方案"""
    user_id = _get_user_id(request)
    scheme = _verify_scheme_owner(db, scheme_id, user_id)

    if req.confirmed:
        scheme.status = "confirmed"
        message = "方案已确认，您可以生成服务手册"
    else:
        scheme.status = "draft"
        message = "方案已取消确认，您可以继续调整"

    db.commit()
    return ApiResponse(data={"scheme_id": scheme_id, "status": scheme.status, "message": message})


@router.post("/{scheme_id}/adjust", response_model=ApiResponse)
async def adjust_scheme(
    scheme_id: int, req: SchemeAdjustRequest, request: Request, db: Session = Depends(get_db)
):
    """调整方案"""
    user_id = _get_user_id(request)
    _verify_scheme_owner(db, scheme_id, user_id)
    agent = get_agent_service()
    result = await agent.adjust_scheme(db, scheme_id, req.adjustment_prompt)
    if "error" in result:
        status_code = 404 if result["error"] == "方案不存在" else 400
        raise HTTPException(status_code=status_code, detail=result["error"])
    return ApiResponse(data=result)


@router.get("/conversation/{conversation_id}", response_model=ApiResponse)
async def get_scheme_by_conversation(
    conversation_id: int, db: Session = Depends(get_db)
):
    """根据对话ID获取当前方案"""
    scheme = (
        db.query(GeneratedScheme)
        .filter(GeneratedScheme.conversation_id == conversation_id)
        .order_by(GeneratedScheme.id.desc())
        .first()
    )
    if not scheme:
        return ApiResponse(data=None)
    return ApiResponse(data=_scheme_to_dict(scheme, db))


def _scheme_to_dict(scheme: GeneratedScheme, db: Session) -> dict:
    """将 ORM 对象转为字典，兼容新旧格式，含关联的 Excel/手册 ID"""
    raw_data = json.loads(scheme.service_list_json or "[]")

    # 兼容新旧格式：新格式存的是完整 scheme_data 对象，旧格式存的是 services 数组
    if isinstance(raw_data, dict):
        services = raw_data.get("services", [])
        schemes = raw_data.get("schemes", [])
    else:
        services = raw_data
        schemes = []

    def _make_item(s):
        return SchemeItemOut(
            name=s.get("name", ""),
            content=s.get("content"),
            times=s.get("times"),
            condition=s.get("condition"),
            standard=s.get("standard"),
            network=s.get("network"),
            cost_price=s.get("cost_price") or s.get("cost"),
            quote_price=s.get("quote_price") or s.get("quote") or s.get("price"),
            price=s.get("price"),
            remark=s.get("remark"),
        )

    result = {
        "id": scheme.id,
        "conversation_id": scheme.conversation_id,
        "scheme_name": scheme.scheme_name,
        "scene": scheme.scene,
        "target_group": scheme.target_group,
        "service_list": [_make_item(s) for s in services],
        "total_cost": float(scheme.total_cost) if scheme.total_cost else 0,
        "total_quote": float(scheme.total_quote) if scheme.total_quote else 0,
        "status": scheme.status,
        "create_time": scheme.create_time,
    }

    # 查找关联的 Excel 报价单和手册 ID
    from database import GeneratedExcel, GeneratedManual
    gen_excel = (
        db.query(GeneratedExcel)
        .filter(GeneratedExcel.scheme_id == scheme.id)
        .first()
    )
    if gen_excel:
        result["excel_id"] = gen_excel.id
    gen_manual = (
        db.query(GeneratedManual)
        .filter(GeneratedManual.scheme_id == scheme.id)
        .first()
    )
    if gen_manual:
        result["manual_id"] = gen_manual.id

    # 如果有 schemes 数组，也一并返回
    if schemes:
        result["schemes"] = []
        for s in schemes:
            svcs = s.get("services", [])
            result["schemes"].append({
                "scheme_name": s.get("scheme_name", ""),
                "scene": s.get("scene"),
                "target_group": s.get("target_group"),
                "service_list": [_make_item(svc) for svc in svcs],
                "total_cost": s.get("total_cost"),
                "total_quote": s.get("total_quote"),
                "unit": s.get("unit"),
            })

    return result
