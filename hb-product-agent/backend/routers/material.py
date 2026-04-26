"""
素材库接口路由
"""
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from database import get_db, Service
from models.schemas import ServiceOut, ServiceSearchRequest, ApiResponse

router = APIRouter()


@router.get("/services", response_model=ApiResponse)
async def list_services(
    keyword: str = Query(None, description="关键词搜索"),
    category: str = Query(None, description="类别过滤"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """获取服务素材列表"""
    query = db.query(Service)
    if keyword:
        query = query.filter(
            Service.name.contains(keyword)
            | Service.description.contains(keyword)
        )
    if category:
        query = query.filter(Service.category == category)

    services = query.limit(limit).all()
    return ApiResponse(
        data=[
            {
                "id": s.id,
                "category": s.category,
                "name": s.name,
                "description": s.description,
                "times": s.times,
                "cost_price": s.cost_price,
            }
            for s in services
        ]
    )


@router.get("/services/{service_id}", response_model=ApiResponse)
async def get_service(service_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    """获取单个服务素材详情"""
    svc = db.query(Service).filter(Service.id == service_id).first()
    if not svc:
        raise HTTPException(status_code=404, detail="服务不存在")
    return ApiResponse(
        data={
            "id": svc.id,
            "category": svc.category,
            "name": svc.name,
            "description": svc.description,
            "process": svc.process,
            "condition": svc.condition,
            "times": svc.times,
            "cost_price": svc.cost_price,
            "usage_rate_small": svc.usage_rate_small,
            "usage_rate_large": svc.usage_rate_large,
            "source_file": svc.source_file,
        }
    )


@router.get("/categories", response_model=ApiResponse)
async def list_categories(db: Session = Depends(get_db)):
    """获取所有服务类别"""
    categories = db.query(Service.category).distinct().all()
    return ApiResponse(data=[c[0] for c in categories if c[0]])
