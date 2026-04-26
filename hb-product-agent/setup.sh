#!/bin/bash
# 本地开发环境设置脚本

set -e

echo "=== 产品 Agent 模块 - 本地开发环境设置 ==="

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请先安装 Python 3.11+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "Python 版本: $PYTHON_VERSION"

# 创建虚拟环境
echo ""
echo ">>> 创建 Python 虚拟环境 (venv)..."
cd backend
if [ -d "venv" ]; then
    echo "虚拟环境已存在，跳过创建"
else
    python3 -m venv venv
    echo "虚拟环境创建完成"
fi

# 激活虚拟环境并安装依赖
echo ""
echo ">>> 安装 Python 依赖..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "Python 依赖安装完成"

# 创建 .env 文件模板
if [ ! -f ".env" ]; then
    echo ""
    echo ">>> 创建 .env 配置文件模板..."
    cat > .env << 'EOF'
# 数据库配置
DB_TYPE=sqlite
DB_URL=sqlite:///./hb_agent.db

# 阿里云百炼配置 (请填写实际值)
BAILIAN_API_KEY=your-api-key-here
BAILIAN_APP_ID=your-app-id-here
BAILIAN_BASE_URL=https://dashscope.aliyuncs.com/api/v1

# 应用配置
APP_DEBUG=true
APP_PORT=8000
EOF
    echo ".env 文件已创建，请编辑填写实际的 API Key"
fi

cd ..

# 前端依赖安装
echo ""
echo ">>> 安装前端依赖..."
cd frontend
if command -v npm &> /dev/null; then
    npm install
    echo "前端依赖安装完成"
else
    echo "警告: 未找到 npm，跳过前端依赖安装"
fi

cd ..

echo ""
echo "=== 设置完成 ==="
echo ""
echo "启动后端:"
echo "  cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000"
echo ""
echo "启动前端:"
echo "  cd frontend && npm run dev"
echo ""
echo "Docker 部署:"
echo "  docker-compose up --build"
echo ""
