"""
服务手册接口路由
"""
import logging
import os
import traceback
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db, GeneratedManual, GeneratedScheme
from models.schemas import GenerateManualRequest, ApiResponse
from services.manual_generator import ManualGenerator

logger = logging.getLogger("manual_router")
router = APIRouter()


@router.post("/generate", response_model=ApiResponse)
async def generate_manual(req: GenerateManualRequest, db: Session = Depends(get_db)):
    """生成服务手册"""
    # 检查方案是否已确认
    scheme = db.query(GeneratedScheme).filter(GeneratedScheme.id == req.scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="方案不存在")
    if scheme.status != "confirmed":
        raise HTTPException(status_code=400, detail="方案未确认，请先确认方案")

    generator = ManualGenerator()
    try:
        result = generator.generate_manual(
            db,
            req.scheme_id,
            selected_scheme_name=req.selected_scheme_name,
            selected_scheme_index=req.selected_scheme_index,
        )
        manual, missing = result
        logger.info(f"服务手册生成成功: scheme_id={req.scheme_id}, manual_id={manual.id}")
        return ApiResponse(
            data={
                "manual_id": manual.id,
                "manual_title": manual.manual_title,
                "version": manual.version,
                "file_path": manual.docx_path,
                "status": manual.status,
                "missing_templates": missing,
                "message": "服务手册生成成功" if not missing else f"服务手册已生成，但以下服务缺少模板：{', '.join(missing)}",
            }
        )
    except ValueError as e:
        logger.warning(f"服务手册业务错误: scheme_id={req.scheme_id}, {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"服务手册生成失败: scheme_id={req.scheme_id}, error={e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@router.get("/{manual_id}", response_model=ApiResponse)
async def get_manual(manual_id: int, db: Session = Depends(get_db)):
    """获取服务手册信息"""
    manual = db.query(GeneratedManual).filter(GeneratedManual.id == manual_id).first()
    if not manual:
        raise HTTPException(status_code=404, detail="手册不存在")
    return ApiResponse(
        data={
            "id": manual.id,
            "scheme_id": manual.scheme_id,
            "manual_title": manual.manual_title,
            "docx_path": manual.docx_path,
            "status": manual.status,
            "create_time": manual.create_time,
        }
    )


@router.get("/{manual_id}/download")
async def download_manual(manual_id: int, db: Session = Depends(get_db)):
    """下载服务手册 docx 文件"""
    manual = db.query(GeneratedManual).filter(GeneratedManual.id == manual_id).first()
    if not manual or not manual.docx_path:
        raise HTTPException(status_code=404, detail="手册文件不存在")

    if not os.path.exists(manual.docx_path):
        raise HTTPException(status_code=404, detail="文件已删除或移动")

    if not manual.docx_path.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="文件类型无效，仅支持 .docx 格式")

    return FileResponse(
        path=manual.docx_path,
        filename=os.path.basename(manual.docx_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
