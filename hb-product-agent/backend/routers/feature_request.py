"""
用户超范围功能需求记录接口
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db, UserFeatureRequest
from models.schemas import ApiResponse

router = APIRouter()


@router.get("/feature-requests", response_model=ApiResponse)
async def list_feature_requests(
    status: str = Query(None, description="状态过滤: pending/reviewed/planned/rejected"),
    limit: int = Query(50, ge=1, le=200, description="返回条数上限"),
    db: Session = Depends(get_db),
):
    """获取用户超范围功能需求记录列表"""
    query = db.query(UserFeatureRequest).order_by(UserFeatureRequest.create_time.desc())
    if status:
        query = query.filter(UserFeatureRequest.status == status)
    records = query.limit(limit).all()
    return ApiResponse(
        data=[
            {
                "id": r.id,
                "user_id": r.user_id,
                "summary": r.request_summary,
                "content": r.request_content,
                "source": r.source,
                "status": r.status,
                "create_time": str(r.create_time),
            }
            for r in records
        ]
    )
