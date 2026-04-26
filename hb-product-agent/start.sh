#!/bin/bash
# 产品精算 Agent 启动脚本
# 先彻底清理僵尸进程，再启动服务

echo "=== 清理旧进程 ==="
BACKEND_PORT=18080
FRONTEND_PORT=15174
# 强制杀掉所有相关端口上的进程
lsof -tiTCP:${BACKEND_PORT} -sTCP:LISTEN 2>/dev/null | xargs kill -9 2>/dev/null
lsof -tiTCP:${FRONTEND_PORT} -sTCP:LISTEN 2>/dev/null | xargs kill -9 2>/dev/null
# 杀残留 vite/esbuild/uvicorn
pkill -9 -f "uvicorn main:app" 2>/dev/null
pkill -9 -f "node.*vite" 2>/dev/null
pkill -9 -f "esbuild.*service" 2>/dev/null
sleep 2

# 确认端口释放
lsof -tiTCP:${BACKEND_PORT} -sTCP:LISTEN 2>/dev/null && echo "⚠️  ${BACKEND_PORT} 仍被占用" || echo "✅ ${BACKEND_PORT} 已释放"
lsof -tiTCP:${FRONTEND_PORT} -sTCP:LISTEN 2>/dev/null && echo "⚠️  ${FRONTEND_PORT} 仍被占用" || echo "✅ ${FRONTEND_PORT} 已释放"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== 启动后端 (port ${BACKEND_PORT}) ==="
cd "$PROJECT_DIR/backend"
if [ -x "$PROJECT_DIR/backend/venv/bin/python" ]; then
  PY_CMD="$PROJECT_DIR/backend/venv/bin/python"
else
  PY_CMD="python3"
fi
# Stream 长连接使用单进程，避免 --reload 双进程造成回调不稳定
nohup "$PY_CMD" -m uvicorn main:app --host 0.0.0.0 --port ${BACKEND_PORT} > /tmp/uvicorn.log 2>&1 &
sleep 3

echo "=== 启动前端 (port ${FRONTEND_PORT}) ==="
cd "$PROJECT_DIR/frontend"
nohup npm run dev -- --host 0.0.0.0 --port ${FRONTEND_PORT} > /tmp/vite.log 2>&1 &
sleep 4

echo ""
echo "=== 验证 ==="
curl -s --max-time 3 http://localhost:${BACKEND_PORT}/health && echo "" || echo "❌ 后端启动失败"
curl -s --max-time 3 http://localhost:${FRONTEND_PORT} | head -1 && echo "" || echo "❌ 前端启动失败"
echo ""
echo "✅ 启动完成"
echo "   前端: http://localhost:${FRONTEND_PORT}"
echo "   后端: http://localhost:${BACKEND_PORT}"
