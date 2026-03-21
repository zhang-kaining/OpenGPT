#!/bin/bash

ROOT="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$ROOT/.pids"
LOG_DIR="$ROOT/logs"
EMBEDDING_GATEWAY_PORT="${EMBEDDING_GATEWAY_PORT:-8101}"
OpenGPT_API_PORT="${OpenGPT_API_PORT:-18789}"
QDRANT_DIR="$ROOT/backend/data/qdrant"
QDRANT_BACKUP_DIR="$ROOT/backend/data/backups"

# ---- 帮助 ----
usage() {
  echo "用法: $0 [start|stop|restart|status|logs|backup]"
  echo "  start    启动服务（前台）"
  echo "  start -d 后台运行"
  echo "  stop     停止后台服务"
  echo "  restart  重启后台服务"
  echo "  status   查看运行状态"
  echo "  logs     实时查看日志"
  echo "  backup   立即备份 qdrant 数据"
}

# ---- 备份 qdrant ----
backup_qdrant() {
  local data_dir="$ROOT/backend/data"
  local qdrant_dirs
  qdrant_dirs=$(ls -1d "$data_dir"/qdrant* 2>/dev/null | xargs -n1 basename 2>/dev/null)
  if [ -z "$qdrant_dirs" ]; then
    echo "[备份] 未找到 qdrant* 数据目录，跳过"
    return 0
  fi

  mkdir -p "$QDRANT_BACKUP_DIR"
  local ts
  ts="$(date +%Y%m%d-%H%M%S)"
  local out="$QDRANT_BACKUP_DIR/qdrant-all-$ts.tar.gz"

  if tar -C "$data_dir" -czf "$out" $qdrant_dirs 2>/dev/null; then
    echo "[备份] 已创建: $out"
  else
    echo "[备份] 创建失败"
    return 1
  fi

  # 仅保留最近 10 份，避免占满磁盘
  local old_files
  old_files="$(ls -1t "$QDRANT_BACKUP_DIR"/qdrant-*.tar.gz "$QDRANT_BACKUP_DIR"/qdrant-all-*.tar.gz 2>/dev/null | awk 'NR>10')"
  if [ -n "$old_files" ]; then
    echo "$old_files" | xargs rm -f
    echo "[备份] 已清理旧备份（保留最近 10 份）"
  fi
}

# ---- 停止 ----
stop_services() {
  local found=false

  # 1. 先按 .pids 文件杀（连子进程一起）
  if [ -f "$PID_FILE" ]; then
    echo "停止服务..."
    while IFS= read -r pid; do
      if kill -0 "$pid" 2>/dev/null; then
        # 先优雅停止，给本地 qdrant 落盘时间
        kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null
        echo "  已发送停止信号 PID $pid"
        found=true
      fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
    # 等待进程优雅退出
    sleep 2
  fi

  # 2. 兜底：按端口清理残留进程（先 TERM，仍存活再 KILL）
  for port in "$OpenGPT_API_PORT" 5173 "$EMBEDDING_GATEWAY_PORT"; do
    local pids
    pids=$(lsof -ti :"$port" 2>/dev/null)
    if [ -n "$pids" ]; then
      echo "$pids" | xargs kill 2>/dev/null
      sleep 1
      local remain
      remain=$(lsof -ti :"$port" 2>/dev/null)
      if [ -n "$remain" ]; then
        echo "$remain" | xargs kill -9 2>/dev/null
      fi
      echo "  已清理端口 $port 残留进程（优雅+兜底）"
      found=true
    fi
  done

  if [ "$found" = true ]; then
    echo "✅ 已停止"
  else
    echo "没有找到运行中的服务"
  fi
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

  echo "=== 启动 OpenGPT ==="
  backup_qdrant

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

  mkdir -p "$LOG_DIR"

  # Embedding Gateway（独立 OpenAI 兼容向量网关）
  cd "$ROOT/backend"
  nohup .venv/bin/uvicorn embedding_gateway.main:app --host 0.0.0.0 --port "$EMBEDDING_GATEWAY_PORT" \
    > "$LOG_DIR/embedding-gateway.log" 2>&1 &
  GATEWAY_PID=$!

  if [ "$daemon" = "true" ]; then
    cd "$ROOT/backend"
    nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$OpenGPT_API_PORT" \
      > "$LOG_DIR/backend.log" 2>&1 &
    BACKEND_PID=$!

    # 等待后端就绪（最多 30 秒）
    echo "[后端] 等待启动..."
    for i in $(seq 1 30); do
      if grep -q "Application startup complete" "$LOG_DIR/backend.log" 2>/dev/null; then
        echo "[后端] 已就绪 ✅"
        break
      fi
      sleep 1
    done

    cd "$ROOT/frontend"
    nohup npm run dev \
      > "$LOG_DIR/frontend.log" 2>&1 &
    FRONTEND_PID=$!

    echo "$BACKEND_PID" > "$PID_FILE"
    echo "$FRONTEND_PID" >> "$PID_FILE"
    echo "$GATEWAY_PID" >> "$PID_FILE"

    sleep 1
    echo ""
    echo "✅ 后台启动完成！"
    echo "   前端: http://localhost:5173"
    echo "   后端: http://localhost:$OpenGPT_API_PORT"
    echo "   向量网关: http://localhost:$EMBEDDING_GATEWAY_PORT/v1/embeddings"
    echo "   日志: $LOG_DIR/"
    echo ""
    echo "查看日志: bash start.sh logs"
    echo "停止服务: bash start.sh stop"
  else
    cd "$ROOT/backend"
    .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$OpenGPT_API_PORT" --reload &
    BACKEND_PID=$!

    cd "$ROOT/frontend"
    npm run dev &
    FRONTEND_PID=$!

    echo ""
    echo "✅ 启动完成！"
    echo "   前端: http://localhost:5173"
    echo "   后端: http://localhost:$OpenGPT_API_PORT"
    echo "   向量网关: http://localhost:$EMBEDDING_GATEWAY_PORT/v1/embeddings"
    echo ""
    echo "按 Ctrl+C 停止所有服务"

    trap "kill $BACKEND_PID $FRONTEND_PID $GATEWAY_PID 2>/dev/null; exit" INT TERM
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
    echo "=== 向量网关日志 ($LOG_DIR/embedding-gateway.log) ==="
    tail -f "$LOG_DIR/embedding-gateway.log" &
    wait
    ;;
  backup)
    backup_qdrant
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
# bash start.sh logsbash start.sh start -d

# # 前台运行（调试用，Ctrl+C 停止）
# bash start.sh start