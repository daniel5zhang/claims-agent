"""
FastAPI 应用入口
"""
import os
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers import chat, scheme, material, manual, excel, pricing, feature_request
from middleware import UserIdMiddleware
from services.task_manager import start_cleanup_scheduler
from services.dingtalk_stream_client import DingtalkStreamClient

# 全局钉钉 Stream 客户端实例（在 lifespan 中管理生命周期）
_dingtalk_client: DingtalkStreamClient | None = None

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    global _dingtalk_client
    # 启动时初始化数据库
    init_db()
    # 启动后台任务清理调度器（每5分钟清理过期任务）
    start_cleanup_scheduler(interval_seconds=300)
    # 启动钉钉 Stream 客户端（后台线程，不阻塞事件循环）
    try:
        _dingtalk_client = DingtalkStreamClient(loop=asyncio.get_running_loop())
        _dingtalk_client.start()
    except Exception as e:
        logger.warning(f"钉钉 Stream 客户端启动失败: {e}")
    yield
    # 关闭时优雅停止钉钉 Stream 客户端
    if _dingtalk_client:
        try:
            _dingtalk_client.stop()
        except Exception as e:
            logger.warning(f"钉钉 Stream 客户端停止异常: {e}")


app = FastAPI(
    title="产品 Agent 方案生成模块",
    description="基于自然语言对话的产品方案生成系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制为 hb_core 域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 用户身份识别中间件
app.add_middleware(UserIdMiddleware)

# 注册路由
app.include_router(chat.router, prefix="/api/chat", tags=["对话"])
app.include_router(scheme.router, prefix="/api/scheme", tags=["方案"])
app.include_router(material.router, prefix="/api/material", tags=["素材库"])
app.include_router(manual.router, prefix="/api/manual", tags=["服务手册"])
app.include_router(excel.router, prefix="/api/excel", tags=["Excel报价单"])
app.include_router(pricing.router, prefix="/api/pricing", tags=["定价引擎"])
app.include_router(feature_request.router, prefix="/api/feature-request", tags=["需求记录"])


@app.get("/health")
async def health_check():
    return {"code": 0, "message": "success", "data": {"status": "ok", "service": "hb-product-agent"}}
