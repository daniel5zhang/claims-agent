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
from routers import chat, scheme, material, manual, excel, pricing
from middleware import UserIdMiddleware
from services.task_manager import start_cleanup_scheduler

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化数据库
    init_db()
    # 启动后台任务清理调度器（每5分钟清理过期任务）
    start_cleanup_scheduler(interval_seconds=300)
    yield


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


@app.get("/health")
async def health_check():
    return {"code": 0, "message": "success", "data": {"status": "ok", "service": "hb-product-agent"}}
