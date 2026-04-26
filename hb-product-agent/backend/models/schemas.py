"""
Pydantic 模型定义
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal


# ========== 对话相关 ==========

class ChatMessage(BaseModel):
    role: str = Field(..., description="角色: user / assistant / system")
    content: str = Field(..., description="消息内容")
    timestamp: Optional[datetime] = Field(default_factory=datetime.now)


class ChatRequest(BaseModel):
    session_id: Optional[str] = Field(None, description="会话ID，空则新建")
    message: str = Field(..., description="用户消息")


class ChatResponse(BaseModel):
    session_id: str
    message: ChatMessage
    scheme: Optional[Dict[str, Any]] = None
    needs_status: str = Field("collecting", description="collecting / complete")


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: List[ChatMessage]
    extracted_needs: Optional[Dict[str, Any]] = None


# ========== 方案相关 ==========

class SchemeItemOut(BaseModel):
    name: str
    content: Optional[str] = None
    times: Optional[str] = None
    condition: Optional[str] = None
    standard: Optional[str] = None
    network: Optional[str] = None
    cost_price: Optional[Decimal] = None
    quote_price: Optional[Decimal] = None
    price: Optional[Decimal] = None
    remark: Optional[str] = None


class GeneratedSchemeOut(BaseModel):
    id: int
    conversation_id: int
    scheme_name: Optional[str] = None
    scene: Optional[str] = None
    target_group: Optional[str] = None
    service_list: List[SchemeItemOut] = []
    total_cost: Optional[Decimal] = None
    total_quote: Optional[Decimal] = None
    status: str = "draft"
    create_time: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SchemeConfirmRequest(BaseModel):
    scheme_id: int
    confirmed: bool


class SchemeAdjustRequest(BaseModel):
    scheme_id: int
    adjustment_prompt: str = Field(..., description="调整要求，如'把心理咨询换成视频问诊'")


# ========== 服务手册相关 ==========

class GenerateManualRequest(BaseModel):
    scheme_id: int
    selected_scheme_name: Optional[str] = Field(
        None, description="可选：指定方案名称（多方案时只生成该方案）"
    )
    selected_scheme_index: Optional[int] = Field(
        None, ge=1, description="可选：指定方案序号（从1开始，多方案时只生成该方案）"
    )


class GenerateExcelRequest(BaseModel):
    scheme_id: int
    selected_scheme_name: Optional[str] = Field(
        None, description="可选：指定方案名称（多方案时只生成该方案）"
    )
    selected_scheme_index: Optional[int] = Field(
        None, ge=1, description="可选：指定方案序号（从1开始，多方案时只生成该方案）"
    )


class ManualOut(BaseModel):
    id: int
    scheme_id: int
    manual_title: Optional[str] = None
    docx_path: Optional[str] = None
    status: str
    create_time: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ========== 素材库相关 ==========

class ServiceOut(BaseModel):
    id: int
    category: Optional[str] = None
    name: str
    description: Optional[str] = None
    times: Optional[str] = None
    cost_price: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)


class ServiceSearchRequest(BaseModel):
    keyword: Optional[str] = None
    category: Optional[str] = None


# ========== 需求提取 ==========

class SessionOut(BaseModel):
    """会话列表项"""
    session_id: str
    title: Optional[str] = None
    status: str = "active"
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None


# ========== 需求提取 ==========

class ExtractedNeeds(BaseModel):
    target_group: Optional[str] = Field(None, description="目标人群")
    budget_range: Optional[str] = Field(None, description="预算区间")
    service_preferences: List[str] = Field(default_factory=list, description="服务偏好")
    scene: Optional[str] = Field(None, description="使用场景")
    scale: Optional[str] = Field(None, description="规模")
    special_requirements: Optional[str] = Field(None, description="特殊要求")


# ========== 通用 ==========

class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[Any] = None
