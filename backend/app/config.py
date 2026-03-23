import errno
import os

from pydantic import BaseModel, ConfigDict


def _default_mem0_dir() -> str:
    return os.path.join(os.path.expanduser("~"), ".mem0")


def _ensure_writable_mem0_path(path: str) -> str:
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        if e.errno in (errno.EACCES, errno.EPERM, errno.EROFS, 30):
            fb = _default_mem0_dir()
            if os.path.abspath(path) != os.path.abspath(fb):
                os.makedirs(fb, exist_ok=True)
                return fb
            raise
        raise
    return path


class Settings(BaseModel):
    """默认值仅来自代码；运行中覆盖来自 data/settings.db，不读 .env。"""

    model_config = ConfigDict(extra="ignore")

    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-06-01"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"

    # 多模型：JSON 数组；active 为其中某个 id
    llm_providers_json: str = "[]"
    active_llm_provider_id: str = ""

    tavily_api_key: str = ""

    embedding_provider: str = "azure"
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = ""
    # 向量模型：JSON 数组；active 为其中某个 id
    embedding_providers_json: str = "[]"
    active_embedding_provider_id: str = ""

    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_default_open_id: str = ""
    feishu_default_folder_token: str = ""
    feishu_wiki_node_token: str = ""
    feishu_wiki_base_url: str = ""

    user_id: str = "default_user"
    max_registered_users: int = 1

    db_path: str = "data/chat.db"
    sqlite_timeout_seconds: float = 30.0

    # JWT 专用密钥；不填则回退到原逻辑（azure key / 占位符）
    jwt_secret: str = ""

    # mem0 历史等；留空则用 ~/.mem0
    mem0_dir: str = ""

    # 与 .env MEMORY_* 一致，用字符串 "0"/"1" 便于前端与 JSON
    memory_enable_legacy_read: str = "0"
    memory_dual_write_legacy: str = "0"
    memory_legacy_model: str = "text-embedding-v4"
    memory_legacy_collection: str = "OpenGPT_memories"
    memory_legacy_path: str = "data/qdrant"


def _coerce_patch_value(key: str, v: object, template: dict) -> object:
    if key not in template:
        return v
    if v is None:
        return None
    ann = type(template[key])
    if ann is str:
        if isinstance(v, bool):
            return "1" if v else "0"
        return str(v).strip() if v is not None else ""
    if ann is bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "yes", "on")
        return bool(v)
    if ann is int:
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v.strip():
            return int(v.strip(), 10)
        return v
    if ann is float:
        if isinstance(v, bool):
            return float(int(v))
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str) and v.strip():
            return float(v.strip())
        return v
    return v


def get_settings() -> Settings:
    from app.services import runtime_config as rc

    base = Settings()
    d = base.model_dump()
    patch = rc.load_raw()
    for k, v in patch.items():
        if k not in d:
            continue
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        d[k] = _coerce_patch_value(k, v, d)
    s = Settings.model_validate(d)

    # 兼容依赖 requires_env 的 Skill：将运行时配置同步到进程环境变量
    _runtime_env = {
        "TAVILY_API_KEY": s.tavily_api_key,
        "FEISHU_APP_ID": s.feishu_app_id,
        "FEISHU_APP_SECRET": s.feishu_app_secret,
    }
    for k, v in _runtime_env.items():
        vv = (v or "").strip()
        if vv:
            os.environ[k] = vv
        else:
            os.environ.pop(k, None)

    raw_mem0 = (s.mem0_dir or "").strip()
    mem0_path = os.path.expanduser(raw_mem0) if raw_mem0 else _default_mem0_dir()
    mem0_path = _ensure_writable_mem0_path(mem0_path)
    os.environ["MEM0_DIR"] = mem0_path

    return s


def reload_runtime_clients() -> None:
    from app.services import azure_openai as ao
    from app.services import memory as mem

    ao.reset_chat_clients()
    mem.reset_memory_clients()
