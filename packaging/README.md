# macOS 桌面试用（自签可省）

适合**自己用**：不必公证、不必 DMG；若要给别人下载再考虑签名与镜像。

## 前提

- 已安装 Node.js（建议 18+）与 Python 3
- `backend/.env` 已配置；`backend/.venv` 已 `pip install -r requirements.txt`
- 前端已构建：`cd frontend && npm install && npm run build`

## 第一次

**请先停掉占用 8000 / 8101 的进程**（例如曾运行过 `bash start.sh start -d`），否则 Electron 连到的可能是「没带静态前端」的旧后端，窗口里只会看到 `{"detail":"Not Found"}`。可先：`bash start.sh stop`。

```bash
cd desktop
npm install
npm start
```

Electron 会启动：

1. 向量网关（默认端口与 `.env` 中 `EMBEDDING_GATEWAY_PORT` 一致，缺省 `8101`）
2. 主 API + 静态页面（`MYGPT_API_PORT` 缺省 `8000`，由程序设置 `MYGPT_STATIC_DIR` 指向 `frontend/dist`）

浏览器里也可直接打开：`http://127.0.0.1:8000/`（需自行先按 `start.sh` 或上述方式启动两个 uvicorn）。

## 环境变量（可选）

| 变量 | 说明 |
|------|------|
| `MYGPT_API_PORT` | 主服务端口，默认 `8000` |
| `EMBEDDING_GATEWAY_PORT` | 向量网关端口，需与 `backend/.env` 里 `EMBEDDING_BASE_URL` 一致 |

## 后端说明

设置环境变量 **`MYGPT_STATIC_DIR`** 为 `frontend/dist` 的绝对路径时，FastAPI 会在同一端口托管前端静态资源（`html=True` 支持 Vue 路由刷新）。

## 进一步打成 .app（可选）

可用 `electron-builder` 等把 `desktop/` 打成 `.app`，并把 `backend/.venv`、`frontend/dist`、`.env` 拷进 `Resources`；体量较大，需单独调 `main.cjs` 里的路径解析。个人使用保持「本机源码 + npm start」最简单。
