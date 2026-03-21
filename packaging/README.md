# macOS 桌面试用（自签可省）

适合**自己用**：不必公证、不必 DMG；若要给别人下载再考虑签名与镜像。

## 前提

- 已安装 Node.js（建议 18+）与 Python 3
- `backend/.env` 已配置；`backend/.venv` 已 `pip install -r requirements.txt`
- 前端已构建：`cd frontend && npm install && npm run build`

## 第一次

**请先停掉占用默认 API 口（`OpenGPT_API_PORT`，缺省 `18789`）/ `8101` 的进程**（例如曾运行过 `bash start.sh start -d`），否则 Electron 连到的可能是「没带静态前端」的旧后端，窗口里只会看到 `{"detail":"Not Found"}`。可先：`bash start.sh stop`。

```bash
cd desktop
npm install
npm start
```

Electron 会启动：

1. 向量网关（默认端口与 `.env` 中 `EMBEDDING_GATEWAY_PORT` 一致，缺省 `8101`）
2. 主 API + 静态页面（`OpenGPT_API_PORT` 缺省 `18789`，由程序设置 `OpenGPT_STATIC_DIR` 指向 `frontend/dist`）

浏览器里也可直接打开：`http://127.0.0.1:18789/`（需自行先按 `start.sh` 或上述方式启动两个 uvicorn）。

## 环境变量（可选）

| 变量 | 说明 |
|------|------|
| `OpenGPT_API_PORT` | 主服务端口，默认 `18789`（`start.sh` / Vite 代理 / Electron 一致） |
| `EMBEDDING_GATEWAY_PORT` | 向量网关端口，需与 `backend/.env` 里 `EMBEDDING_BASE_URL` 一致 |

## 后端说明

设置环境变量 **`OpenGPT_STATIC_DIR`** 为 `frontend/dist` 的绝对路径时，FastAPI 会在同一端口托管前端静态资源（`html=True` 支持 Vue 路由刷新）。

## 安装版（可选）

已内置 `electron-builder` 配置，支持把 `backend`、`frontend/dist` 与图标一起打进安装版资源目录。

```bash
cd desktop
npm install

# 生成可直接双击运行的 .app（不产 DMG）
npm run pack:dir

# 生成 DMG（安装包）
npm run pack:mac
```

输出目录：`desktop/dist/`

- `pack:dir`：生成 `dist/mac-arm64/OpenGPT.app`（适合本机验证）
- `pack:mac`：生成 `dist/*.dmg`（适合像普通 App 一样安装）

安装版会把运行日志写到用户目录（`~/Library/Application Support/OpenGPT/logs`），不会写入 `.app` 内部只读目录。
