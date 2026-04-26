"""
Excel 报价单接口路由
"""
import logging
import os
import traceback
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db, GeneratedExcel, GeneratedScheme
from models.schemas import GenerateExcelRequest, ApiResponse
from services.excel_generator import ExcelGenerator

logger = logging.getLogger("excel_router")
router = APIRouter()


@router.post("/generate", response_model=ApiResponse)
async def generate_excel(req: GenerateExcelRequest, db: Session = Depends(get_db)):
    """生成 Excel 报价单"""
    scheme = db.query(GeneratedScheme).filter(GeneratedScheme.id == req.scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="方案不存在")
    if scheme.status != "confirmed":
        raise HTTPException(status_code=400, detail="方案未确认，请先确认方案")

    generator = ExcelGenerator()
    try:
        excel = generator.generate_excel(
            db,
            req.scheme_id,
            selected_scheme_name=req.selected_scheme_name,
            selected_scheme_index=req.selected_scheme_index,
        )
        db.commit()
        logger.info(f"Excel 生成成功: scheme_id={req.scheme_id}, excel_id={excel.id}")
        return ApiResponse(
            data={
                "excel_id": excel.id,
                "excel_title": excel.excel_title,
                "version": excel.version,
                "file_path": excel.excel_path,
                "status": excel.status,
                "message": "Excel报价单生成成功",
            }
        )
    except ValueError as e:
        db.rollback()
        logger.warning(f"Excel 生成业务错误: scheme_id={req.scheme_id}, {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"Excel 生成失败: scheme_id={req.scheme_id}, error={e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@router.get("/{excel_id}", response_model=ApiResponse)
async def get_excel(excel_id: int, db: Session = Depends(get_db)):
    """获取 Excel 报价单信息"""
    excel = db.query(GeneratedExcel).filter(GeneratedExcel.id == excel_id).first()
    if not excel:
        raise HTTPException(status_code=404, detail="报价单不存在")
    return ApiResponse(
        data={
            "id": excel.id,
            "scheme_id": excel.scheme_id,
            "excel_title": excel.excel_title,
            "excel_path": excel.excel_path,
            "status": excel.status,
            "create_time": excel.create_time,
        }
    )


@router.get("/{excel_id}/download")
async def download_excel(excel_id: int, db: Session = Depends(get_db)):
    """下载 Excel 报价单文件"""
    excel = db.query(GeneratedExcel).filter(GeneratedExcel.id == excel_id).first()
    if not excel or not excel.excel_path:
        raise HTTPException(status_code=404, detail="报价单文件不存在")

    if not os.path.exists(excel.excel_path):
        raise HTTPException(status_code=404, detail="文件已删除或移动")

    if not excel.excel_path.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="文件类型无效，仅支持 .xlsx 格式")

    return FileResponse(
        path=excel.excel_path,
        filename=os.path.basename(excel.excel_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
