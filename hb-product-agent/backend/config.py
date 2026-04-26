"""
中央配置模块
统一从 .env 文件加载配置，所有模块从此导入，避免各自重复加载。
"""
import os
from dotenv import load_dotenv

# 只加载一次 .env
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)

# --- 百炼 API ---
BAILIAN_API_KEY = os.getenv("BAILIAN_API_KEY", "")
BAILIAN_APP_ID = os.getenv("BAILIAN_APP_ID", "")
BAILIAN_BASE_URL = os.getenv(
    "BAILIAN_BASE_URL", "https://dashscope.aliyuncs.com/api/v1"
)

# --- 数据库 ---
# 开发用 SQLite，生产用 seekdb (OceanBase MySQL 协议)
DB_TYPE = os.getenv("DB_TYPE", "sqlite")
DB_URL = os.getenv("DB_URL", "sqlite:///./hb_agent.db")

SEEKDB_PATH = os.getenv("SEEKDB_PATH", "./seekdb_data")
SEEKDB_DB = os.getenv("SEEKDB_DB", "product_agent")

# --- 应用 ---
APP_DEBUG = os.getenv("APP_DEBUG", "true").lower() == "true"
APP_PORT = int(os.getenv("APP_PORT", "8000"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

# --- 模板 & 输出目录 ---
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATES_DIR = os.path.join(_PROJECT_ROOT, "templates", "manual")
OUTPUT_DIR = os.path.join(_PROJECT_ROOT, "output")
OUTPUT_EXCELS_DIR = os.path.join(_PROJECT_ROOT, "output", "excels")
OUTPUT_MANUALS_DIR = os.path.join(_PROJECT_ROOT, "output", "manuals")

# 兼容旧路径：旧的二进制 docx 模板（废弃中）
MANUAL_TEMPLATE_NAME = os.getenv(
    "MANUAL_TEMPLATE_NAME",
    "8.职工家庭防癌抗癌保障卡健康管理服务手册（个人尊享版）.docx",
)

# --- 百炼模型 ---
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3.6-plus")

# 纯文本模型列表（走 text-generation 端点）
TEXT_MODELS = {
    "qwen-turbo", "qwen-plus", "qwen-max",
    "qwen-max-longcontext", "qwen3.6-plus", "qwen3.6-max",
}

# 多模态模型列表（走 multimodal-generation 端点）
MULTIMODAL_MODELS = {
    "qwen-vl-plus", "qwen-vl-max", "qwen3-vl-plus",
}
