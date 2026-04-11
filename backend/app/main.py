import logging
import os

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.conversation import init_db
from app.services.auth import init_users_table
from app.services.note import init_note_tables
from app.services.feishu_binding import init_feishu_binding_tables
from app.services.skill_manager import get_skill_manager
from app.services.mcp_manager import get_mcp_manager
from app.services.feishu_event_client import get_feishu_event_client
from app.routers import auth, chat, conversations, folders, memory, news, notes, settings_runtime, skills, file_memory
from app.services import feishu as feishu_service

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_users_table()
    await init_note_tables()
    await init_feishu_binding_tables()
    get_skill_manager().load()
    await get_mcp_manager().load()
    
    feishu_client = get_feishu_event_client()
    await feishu_client.start()
    
    yield
    
    await feishu_client.stop()


app = FastAPI(title="OpenGPT API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(folders.router)
app.include_router(memory.router)
app.include_router(news.router)
app.include_router(notes.router)
app.include_router(settings_runtime.router)
app.include_router(skills.router)
app.include_router(file_memory.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/feishu/permissions")
async def feishu_permissions():
    """查询当前飞书应用信息与权限相关接口返回（用于排查写文档 403）。需已配置 FEISHU_APP_ID/SECRET。"""
    if not feishu_service.settings.feishu_app_id or not feishu_service.settings.feishu_app_secret:
        return {"error": "未配置飞书应用"}
    try:
        return await feishu_service.get_app_permissions_info()
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/feishu/event-status")
async def feishu_event_status():
    """查询飞书事件客户端状态"""
    feishu_client = get_feishu_event_client()
    return {
        "running": feishu_client.is_running(),
        "configured": bool(get_settings().feishu_app_id and get_settings().feishu_app_secret)
    }


_static = os.environ.get("OpenGPT_STATIC_DIR", "").strip()
if _static and os.path.isdir(_static):
    class _HtmlNoCacheMiddleware(BaseHTTPMiddleware):
        """对 HTML 响应禁止缓存，避免 Electron webview 缓存旧版前端。"""
        async def dispatch(self, request: Request, call_next):
            response: Response = await call_next(request)
            ct = (response.headers.get("content-type") or "")
            if "text/html" in ct:
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers["Pragma"] = "no-cache"
            return response

    app.add_middleware(_HtmlNoCacheMiddleware)
    app.mount("/", StaticFiles(directory=_static, html=True), name="spa")
