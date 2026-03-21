#!/usr/bin/env bash
# 将 desktop/build/app-icon-source.png（建议 512～1024 正方形 PNG）生成 app-icon-1024.png、icon.iconset 与 icon.icns
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build"
ICONSET="$BUILD/icon.iconset"
SRC="$BUILD/app-icon-source.png"
[[ -f "$SRC" ]] || { echo "缺少 $SRC"; exit 1; }
mkdir -p "$ICONSET"
sips -z 1024 1024 "$SRC" --out "$BUILD/app-icon-1024.png" >/dev/null
S="$BUILD/app-icon-1024.png"
sips -z 16 16 "$S" --out "$ICONSET/icon_16x16.png" >/dev/null
sips -z 32 32 "$S" --out "$ICONSET/icon_16x16@2x.png" >/dev/null
sips -z 32 32 "$S" --out "$ICONSET/icon_32x32.png" >/dev/null
sips -z 64 64 "$S" --out "$ICONSET/icon_32x32@2x.png" >/dev/null
sips -z 128 128 "$S" --out "$ICONSET/icon_128x128.png" >/dev/null
sips -z 256 256 "$S" --out "$ICONSET/icon_128x128@2x.png" >/dev/null
sips -z 256 256 "$S" --out "$ICONSET/icon_256x256.png" >/dev/null
sips -z 512 512 "$S" --out "$ICONSET/icon_256x256@2x.png" >/dev/null
sips -z 512 512 "$S" --out "$ICONSET/icon_512x512.png" >/dev/null
sips -z 1024 1024 "$S" --out "$ICONSET/icon_512x512@2x.png" >/dev/null
iconutil -c icns "$ICONSET" -o "$BUILD/icon.icns"
echo "OK: $BUILD/app-icon-1024.png + $BUILD/icon.icns"
