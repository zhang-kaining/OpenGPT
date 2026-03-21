#!/usr/bin/env bash
# 一键：构建前端 → 打包 Electron（.app 或 DMG）。在项目根目录执行：bash scripts/build-desktop-app.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="dmg"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir) MODE="dir"; shift ;;
    --dmg) MODE="dmg"; shift ;;
    -h | --help)
      echo "用法: bash scripts/build-desktop-app.sh [--dir | --dmg]"
      echo "  --dir  只生成 .app（desktop/dist/mac-*/OpenGPT.app），较快"
      echo "  --dmg  生成 DMG 安装包（默认）"
      exit 0
      ;;
    *)
      echo "未知参数: $1（试 --help）" >&2
      exit 1
      ;;
  esac
done

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "缺少命令: $1" >&2
    exit 1
  }
}

need_cmd node
need_cmd npm

echo "==> [1/4] 前端：npm install + build"
cd "$ROOT/frontend"
npm install
npm run build

echo "==> [2/4] Desktop：npm install"
cd "$ROOT/desktop"
npm install

if [[ "$(uname -s)" == "Darwin" ]] && [[ -f "$ROOT/desktop/build/app-icon-source.png" ]]; then
  echo "==> [3/4] macOS：从 app-icon-source.png 刷新 icon.icns"
  npm run icons:mac
else
  echo "==> [3/4] 跳过图标（非 macOS 或无 desktop/build/app-icon-source.png）"
fi

echo "==> [4/4] Electron 打包"
if [[ "$MODE" == "dir" ]]; then
  npm run pack:dir
  echo "完成：$ROOT/desktop/dist/ 下查看 OpenGPT.app"
else
  npm run pack:mac
  echo "完成：$ROOT/desktop/dist/ 下查看 .dmg（及 .app）"
fi
