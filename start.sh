#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=== 启动 MyGPT ==="

# 后端
cd "$ROOT/backend"
if [ ! -d ".venv" ]; then
  echo "[后端] 创建虚拟环境..."
  python3 -m venv .venv
fi
source .venv/bin/activate
echo "[后端] 安装依赖..."
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
  echo "[后端] 未找到 .env，请复制 .env.example 并填写配置"
  cp .env.example .env
  echo "  已创建 .env，请编辑后重新运行"
  exit 1
fi

mkdir -p data data/mem0
echo "[后端] 启动 FastAPI (端口 8000)..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# 前端
cd "$ROOT/frontend"
echo "[前端] 启动 Vite 开发服务器 (端口 5173)..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ 启动完成！"
echo "   前端: http://localhost:5173"
echo "   后端: http://localhost:8000"
echo "   API文档: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
