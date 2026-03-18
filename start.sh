#!/bin/bash

ROOT="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$ROOT/.pids"
LOG_DIR="$ROOT/logs"

# ---- 帮助 ----
usage() {
  echo "用法: $0 [start|stop|restart|status|logs]"
  echo "  start    启动服务（前台）"
  echo "  start -d 后台运行"
  echo "  stop     停止后台服务"
  echo "  restart  重启后台服务"
  echo "  status   查看运行状态"
  echo "  logs     实时查看日志"
}

# ---- 停止 ----
stop_services() {
  if [ ! -f "$PID_FILE" ]; then
    echo "没有找到运行中的服务"
    return 0
  fi
  echo "停止服务..."
  while IFS= read -r pid; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null
      echo "  已停止 PID $pid"
    fi
  done < "$PID_FILE"
  rm -f "$PID_FILE"
  echo "✅ 已停止"
}

# ---- 状态 ----
status_services() {
  if [ ! -f "$PID_FILE" ]; then
    echo "服务未运行"
    return 0
  fi
  echo "运行中的进程："
  while IFS= read -r pid; do
    if kill -0 "$pid" 2>/dev/null; then
      echo "  PID $pid ✅ 运行中"
    else
      echo "  PID $pid ❌ 已退出"
    fi
  done < "$PID_FILE"
}

# ---- 启动核心逻辑 ----
start_services() {
  local daemon=$1

  echo "=== 启动 MyGPT ==="

  # 后端
  cd "$ROOT/backend"
  if [ ! -d ".venv" ]; then
    echo "[后端] 创建虚拟环境..."
    python3 -m venv .venv
  fi
  echo "[后端] 安装依赖..."
  .venv/bin/pip install -q -r requirements.txt

  if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "[后端] 未找到 .env，已创建，请编辑后重新运行"
    exit 1
  fi
  mkdir -p data/mem0

  # 前端
  cd "$ROOT/frontend"
  if [ ! -d "node_modules" ]; then
    echo "[前端] 安装 npm 依赖..."
    npm install
  fi

  if [ "$daemon" = "true" ]; then
    mkdir -p "$LOG_DIR"
    cd "$ROOT/backend"
    nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 \
      > "$LOG_DIR/backend.log" 2>&1 &
    BACKEND_PID=$!

    cd "$ROOT/frontend"
    nohup npm run dev \
      > "$LOG_DIR/frontend.log" 2>&1 &
    FRONTEND_PID=$!

    echo "$BACKEND_PID" > "$PID_FILE"
    echo "$FRONTEND_PID" >> "$PID_FILE"

    sleep 1
    echo ""
    echo "✅ 后台启动完成！"
    echo "   前端: http://localhost:5173"
    echo "   后端: http://localhost:8000"
    echo "   日志: $LOG_DIR/"
    echo ""
    echo "查看日志: bash start.sh logs"
    echo "停止服务: bash start.sh stop"
  else
    cd "$ROOT/backend"
    .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
    BACKEND_PID=$!

    cd "$ROOT/frontend"
    npm run dev &
    FRONTEND_PID=$!

    echo ""
    echo "✅ 启动完成！"
    echo "   前端: http://localhost:5173"
    echo "   后端: http://localhost:8000"
    echo ""
    echo "按 Ctrl+C 停止所有服务"

    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
    wait
  fi
}

# ---- 入口 ----
CMD="${1:-start}"
case "$CMD" in
  start)
    if [ "$2" = "-d" ]; then
      start_services true
    else
      start_services false
    fi
    ;;
  stop)
    stop_services
    ;;
  restart)
    stop_services
    sleep 1
    start_services true
    ;;
  status)
    status_services
    ;;
  logs)
    if [ ! -d "$LOG_DIR" ]; then
      echo "没有日志文件，请先后台启动：bash start.sh start -d"
      exit 1
    fi
    echo "=== 后端日志 ($LOG_DIR/backend.log) ==="
    tail -f "$LOG_DIR/backend.log" &
    echo "=== 前端日志 ($LOG_DIR/frontend.log) ==="
    tail -f "$LOG_DIR/frontend.log" &
    wait
    ;;
  *)
    usage
    exit 1
    ;;
esac



# # 后台运行（最常用）
# bash start.sh start -d

# # 停止
# bash start.sh stop

# # 重启
# bash start.sh restart

# # 查看是否在运行
# bash start.sh status

# # 实时查看日志
# bash start.sh logs

# # 前台运行（调试用，Ctrl+C 停止）
# bash start.sh start