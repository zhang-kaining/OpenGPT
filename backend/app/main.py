import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.services.conversation import init_db
from app.services.skill_manager import get_skill_manager
from app.services.mcp_manager import get_mcp_manager
from app.routers import chat, conversations, memory, skills

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化数据库
    await init_db()
    # 加载 Skills
    get_skill_manager().load()
    # 加载 MCP（异步，失败不影响启动）
    await get_mcp_manager().load()
    yield


app = FastAPI(title="MyGPT API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(memory.router)
app.include_router(skills.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
