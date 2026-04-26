#!/bin/bash
# 产品精算 Agent 启动脚本
# 先彻底清理僵尸进程，再启动服务

echo "=== 清理旧进程 ==="
# 强制杀掉所有相关端口上的进程
lsof -tiTCP:8000 -sTCP:LISTEN 2>/dev/null | xargs kill -9 2>/dev/null
lsof -tiTCP:5173 -sTCP:LISTEN 2>/dev/null | xargs kill -9 2>/dev/null
# 杀残留 vite/esbuild/uvicorn
pkill -9 -f "uvicorn main:app" 2>/dev/null
pkill -9 -f "node.*vite" 2>/dev/null
pkill -9 -f "esbuild.*service" 2>/dev/null
sleep 2

# 确认端口释放
lsof -tiTCP:8000 -sTCP:LISTEN 2>/dev/null && echo "⚠️  8000 仍被占用" || echo "✅ 8000 已释放"
lsof -tiTCP:5173 -sTCP:LISTEN 2>/dev/null && echo "⚠️  5173 仍被占用" || echo "✅ 5173 已释放"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== 启动后端 (port 8000) ==="
cd "$PROJECT_DIR/backend"
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload > /tmp/uvicorn.log 2>&1 &
sleep 3

echo "=== 启动前端 (port 5173) ==="
cd "$PROJECT_DIR/frontend"
nohup npm run dev -- --host 0.0.0.0 > /tmp/vite.log 2>&1 &
sleep 4

echo ""
echo "=== 验证 ==="
curl -s --max-time 3 http://localhost:8000/health && echo "" || echo "❌ 后端启动失败"
curl -s --max-time 3 http://localhost:5173 | head -1 && echo "" || echo "❌ 前端启动失败"
echo ""
echo "✅ 启动完成"
echo "   前端: http://localhost:5173"
echo "   后端: http://localhost:8000"
