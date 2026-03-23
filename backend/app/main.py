import logging
import os

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.services.conversation import init_db
from app.services.auth import init_users_table
from app.services.note import init_note_tables
from app.services.skill_manager import get_skill_manager
from app.services.mcp_manager import get_mcp_manager
from app.routers import auth, chat, conversations, folders, memory, news, notes, settings_runtime, skills
from app.services import feishu as feishu_service

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_users_table()
    await init_note_tables()
    # 加载 Skills
    get_skill_manager().load()
    # 加载 MCP（异步，失败不影响启动）
    await get_mcp_manager().load()
    yield


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


# 桌面 / 单端口部署：设置 OpenGPT_STATIC_DIR 为 frontend 构建目录（含 index.html）
_static = os.environ.get("OpenGPT_STATIC_DIR", "").strip()
if _static and os.path.isdir(_static):
    app.mount("/", StaticFiles(directory=_static, html=True), name="spa")
