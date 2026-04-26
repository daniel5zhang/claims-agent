"""
后台任务管理器（内存存储，适合单实例部署）
生产环境可替换为 Redis + Celery
"""
import uuid
import json
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal

# 任务存储: task_id -> {status, result, created_at}
_tasks: Dict[str, Dict[str, Any]] = {}


def _make_serializable(obj: Any, depth: int = 0, _seen: set = None) -> Any:
    """将任意对象转为 JSON 兼容的普通 Python 类型，解决循环引用和 Decimal 问题"""
    # 防止循环引用：跟踪已访问的对象 ID
    if _seen is None:
        _seen = set()
    
    obj_id = id(obj)
    if obj_id in _seen:
        return f"<circular:{type(obj).__name__}>"
    
    if depth > 20:
        return f"<max_depth:{type(obj).__name__}>"
    
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    
    if isinstance(obj, Decimal):
        return float(str(obj))
    
    if isinstance(obj, datetime):
        return obj.isoformat()
    
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    
    if isinstance(obj, dict):
        _seen.add(obj_id)
        result = {}
        for k, v in obj.items():
            try:
                result[str(k) if not isinstance(k, str) else k] = _make_serializable(v, depth + 1, _seen)
            except Exception:
                result[str(k) if not isinstance(k, str) else k] = f"<error:{type(v).__name__}>"
        return result
    
    if isinstance(obj, (list, tuple)):
        _seen.add(obj_id)
        result = []
        for item in obj:
            try:
                result.append(_make_serializable(item, depth + 1, _seen))
            except Exception:
                result.append(f"<error:{type(item).__name__}>")
        return result
    
    # 尝试通过 __dict__ 转换（用于 Pydantic 模型、SQLAlchemy 模型等）
    if hasattr(obj, "__dict__"):
        _seen.add(obj_id)
        result = {}
        for k, v in obj.__dict__.items():
            if k.startswith("_"):
                continue
            try:
                result[k] = _make_serializable(v, depth + 1, _seen)
            except Exception:
                result[k] = f"<error:{type(v).__name__}>"
        return result
    
    # 尝试 __slots__
    if hasattr(obj, "__slots__"):
        _seen.add(obj_id)
        result = {}
        for k in obj.__slots__:
            try:
                v = getattr(obj, k, None)
                result[k] = _make_serializable(v, depth + 1, _seen)
            except Exception:
                result[k] = f"<error:slot:{k}>"
        return result
    
    # 其他类型尝试转 str
    try:
        return str(obj)
    except Exception:
        return f"<unhandled:{type(obj).__name__}>"


def create_task() -> str:
    """创建新任务，返回 task_id"""
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        "status": "pending",
        "result": None,
        "error": None,
        "created_at": datetime.now(),
    }
    return task_id


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """获取任务状态"""
    task = _tasks.get(task_id)
    if task and task["status"] == "pending":
        # 检查是否超时（10分钟）
        if datetime.now() - task["created_at"] > timedelta(minutes=10):
            task["status"] = "timeout"
            task["error"] = "任务处理超时"
    return task


def set_task_result(task_id: str, result: Any):
    """设置任务结果"""
    if task_id in _tasks:
        _tasks[task_id]["status"] = "completed"
        _tasks[task_id]["result"] = _make_serializable(result)


def set_task_error(task_id: str, error: str):
    """设置任务错误"""
    if task_id in _tasks:
        _tasks[task_id]["status"] = "failed"
        _tasks[task_id]["error"] = error


def cleanup_old_tasks():
    """清理超过30分钟的任务"""
    cutoff = datetime.now() - timedelta(minutes=30)
    to_remove = [tid for tid, t in _tasks.items() if t["created_at"] < cutoff]
    for tid in to_remove:
        del _tasks[tid]


# 用于注册周期性清理的 asyncio 任务句柄
_cleanup_handle: Optional[asyncio.Task] = None


async def _cleanup_loop(interval_seconds: int = 300):
    """后台周期性清理过期任务（默认每5分钟）"""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            cleanup_old_tasks()
        except Exception:
            pass


def start_cleanup_scheduler(interval_seconds: int = 300):
    """启动后台任务清理调度器（应在应用启动时调用）"""
    global _cleanup_handle
    if _cleanup_handle is None or _cleanup_handle.done():
        _cleanup_handle = asyncio.create_task(_cleanup_loop(interval_seconds))
