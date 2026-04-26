"""
对话接口路由
"""
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db, Conversation
from models.schemas import ChatRequest, ChatResponse, ChatHistoryResponse, ApiResponse, SessionOut
from services.agent_service import get_agent_service
from services.task_manager import create_task, get_task, set_task_result, set_task_error

logger = logging.getLogger("chat_router")

router = APIRouter()

# 全局保持对后台任务的引用，防止被 GC 导致协程未执行
_background_tasks = set()


def _get_user_id(request: Request) -> str:
    """从请求状态中获取 user_id"""
    return getattr(request.state, "user_id", "")


@router.get("/sessions", response_model=ApiResponse)
async def list_sessions(request: Request, db: Session = Depends(get_db)):
    """获取当前用户的所有会话列表"""
    user_id = _get_user_id(request)
    conversations = db.query(Conversation).filter(
        Conversation.user_id == user_id
    ).order_by(Conversation.id.desc()).all()
    sessions = []
    for conv in conversations:
        sessions.append(SessionOut(
            session_id=conv.session_id,
            title=conv.title or "未命名会话",
            status=conv.status or "active",
            create_time=conv.create_time,
            update_time=conv.update_time,
        ))
    return ApiResponse(data=sessions)


@router.delete("/sessions/{session_id}", response_model=ApiResponse)
async def delete_session(session_id: str, request: Request, db: Session = Depends(get_db)):
    """删除指定会话"""
    user_id = _get_user_id(request)
    conv = db.query(Conversation).filter(
        Conversation.session_id == session_id,
        Conversation.user_id == user_id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    db.delete(conv)
    db.commit()
    return ApiResponse(data={"message": "会话已删除"})


@router.post("/send", response_model=ApiResponse)
async def send_message(req: ChatRequest, request: Request, db: Session = Depends(get_db)):
    """发送消息，获取 Agent 回复（同步等待）"""
    try:
        user_id = _get_user_id(request)
        agent = get_agent_service()
        result = await agent.process_message(db, req.session_id, req.message, user_id=user_id)
        return ApiResponse(data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send-async", response_model=ApiResponse)
async def send_message_async(
    req: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """发送消息，后台异步执行（前端轮询获取结果）"""
    user_id = _get_user_id(request)
    task_id = create_task()

    async def run_task():
        from database import SessionLocal
        db_local = SessionLocal()
        try:
            logger.info(f"[async_task] task_id={task_id} 开始处理")
            agent = get_agent_service()
            result = await agent.process_message(db_local, req.session_id, req.message, user_id=user_id)
            logger.info(f"[async_task] task_id={task_id} process_message 完成")
            # 预先序列化测试，提前暴露问题
            import json
            try:
                json.dumps(result, ensure_ascii=False, default=str)
                logger.info(f"[async_task] task_id={task_id} JSON 序列化成功")
            except Exception:
                from services.task_manager import _make_serializable
                result = _make_serializable(result)
                logger.info(f"[async_task] task_id={task_id} 使用 _make_serializable 兜底")
            set_task_result(task_id, result)
            logger.info(f"[async_task] task_id={task_id} 结果已存储")
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"[async_task] task_id={task_id} 失败: {error_msg}")
            set_task_error(task_id, error_msg)
        finally:
            db_local.close()

    task = asyncio.create_task(run_task())
    _background_tasks.add(task)

    def on_done(t):
        _background_tasks.discard(t)
        if t.exception():
            import traceback
            set_task_error(task_id, str(t.exception()) or traceback.format_exc())

    task.add_done_callback(on_done)
    return ApiResponse(data={"task_id": task_id, "message": "任务已提交，请轮询获取结果"})


@router.get("/task/{task_id}", response_model=ApiResponse)
async def get_task_status(task_id: str):
    """获取异步任务状态"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ApiResponse(data={
        "task_id": task_id,
        "status": task["status"],
        "result": task["result"],
        "error": task["error"],
    })


@router.post("/send-stream")
async def send_message_stream(req: ChatRequest, request: Request, db: Session = Depends(get_db)):
    """发送消息，流式获取 Agent 回复 (SSE)"""
    user_id = _get_user_id(request)
    agent = get_agent_service()
    result = await agent.process_message(db, req.session_id, req.message, user_id=user_id)
    return ApiResponse(data=result)


@router.get("/history/{session_id}", response_model=ApiResponse)
async def get_history(session_id: str, request: Request, db: Session = Depends(get_db)):
    """获取对话历史"""
    user_id = _get_user_id(request)
    agent = get_agent_service()
    history = agent.get_conversation_history(db, session_id, user_id=user_id)
    if not history:
        raise HTTPException(status_code=404, detail="会话不存在")
    return ApiResponse(data=history)
