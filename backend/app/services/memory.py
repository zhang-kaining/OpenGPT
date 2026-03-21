import hashlib
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from dotenv import load_dotenv

# mem0 读 MEM0_DIR；由 app.config 在 import 时解析（含不可写路径回退到 ~/.mem0）
load_dotenv()
import app.config as _app_config  # noqa: F401

from mem0 import Memory
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
_mem0_dir = os.environ.get("MEM0_DIR", os.path.join(os.path.expanduser("~"), ".mem0"))

_memory: Memory | None = None
_legacy_memory: Memory | None = None
_table_ready = False
_SQLITE_BUSY_MS = 30000
# 对话检索除向量外，追加最近几条本地记忆，避免「我是谁」等与记忆正文 embedding 不相近时搜不到
_RECENT_MEMORY_SUPPLEMENT = 3
_RECENT_MEMORY_POOL = 40


def _db_connect() -> sqlite3.Connection:
    """与 aiosqlite 共用 chat.db 时减少锁竞争。"""
    conn = sqlite3.connect(settings.db_path, timeout=_SQLITE_BUSY_MS / 1000.0)
    conn.execute(f"PRAGMA busy_timeout={_SQLITE_BUSY_MS}")
    return conn


def _stable_memory_row_id(user_id: str, memory_text: str) -> str:
    """主键：勿用 mem0 返回的 '0'/'1'，多轮请求会重复导致 UNIQUE 冲突。"""
    h = hashlib.sha256(f"{user_id}\n{memory_text}".encode("utf-8")).hexdigest()
    return f"um_{h}"

# DashScope OpenAI 兼容接口当前只支持文本 embedding 模型。
# 允许用户填写多模态模型名时自动降级到可用文本模型，避免启动/检索报错。
_DASHSCOPE_MODEL_FALLBACKS = {
    "qwen3-vl-embedding": "text-embedding-v4",
    "tongyi-embedding-vision-plus": "text-embedding-v4",
}

# Embedding provider 默认配置
_PROVIDER_DEFAULTS = {
    "azure": {
        "model": settings.azure_openai_embedding_deployment or "text-embedding-3-small",
        "base_url": None,
    },
    "dashscope": {
        "model": "text-embedding-v3",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "zhipu": {
        "model": "embedding-3",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
    },
    "ollama": {
        "model": "nomic-embed-text",
        "base_url": "http://localhost:11434/v1",
    },
}


def _build_collection_name(provider: str, model: str) -> str:
    """
    按 provider + model 生成稳定 collection 名，避免不同向量维度写到同一集合。
    例如:
      my_gpt_memories_dashscope_text_embedding_v4
      my_gpt_memories_dashscope_multimodal_embedding_v1
    """
    p = re.sub(r"[^a-zA-Z0-9]+", "_", (provider or "unknown")).strip("_").lower()
    m = re.sub(r"[^a-zA-Z0-9]+", "_", (model or "default")).strip("_").lower()
    name = f"my_gpt_memories_{p}_{m}"
    return name[:120]


def _build_store_path(provider: str, model: str) -> str:
    """
    按 provider + model 隔离 qdrant 本地存储目录，避免 mem0 内部集合（如 mem0migrations）
    在不同向量维度之间冲突。
    """
    p = re.sub(r"[^a-zA-Z0-9]+", "_", (provider or "unknown")).strip("_").lower()
    m = re.sub(r"[^a-zA-Z0-9]+", "_", (model or "default")).strip("_").lower()
    ns = f"{p}_{m}"[:80]
    return f"data/qdrant_{ns}"


def _build_config_with(provider: str, model: str, base_url: str | None, collection_name: str, store_path: str) -> dict:
    # 仅在使用 DashScope 官方 OpenAI 兼容地址时做模型降级。
    # 若 base_url 指向自建网关（如 http://127.0.0.1:8101/v1），则保留原模型名透传。
    use_dashscope_compat = (not base_url) or ("dashscope.aliyuncs.com/compatible-mode" in base_url)
    if provider == "dashscope" and use_dashscope_compat and model in _DASHSCOPE_MODEL_FALLBACKS:
        fallback_model = _DASHSCOPE_MODEL_FALLBACKS[model]
        logger.warning(
            "embedding 模型 %s 不支持 DashScope OpenAI 兼容接口，自动降级为 %s",
            model,
            fallback_model,
        )
        model = fallback_model

    if provider == "azure":
        embedder = {
            "provider": "azure_openai",
            "config": {
                "model": model,
                "azure_kwargs": {
                    "azure_deployment": model,
                    "api_version": settings.azure_openai_api_version,
                    "azure_endpoint": settings.azure_openai_endpoint,
                    "api_key": settings.azure_openai_api_key,
                },
            },
        }
    else:
        # dashscope / zhipu / ollama 均兼容 OpenAI 接口
        api_key = settings.embedding_api_key or "ollama"  # ollama 不需要真实 key
        embedder_cfg: dict = {"model": model, "api_key": api_key}
        if base_url:
            embedder_cfg["openai_base_url"] = base_url
        embedder = {"provider": "openai", "config": embedder_cfg}

    logger.info("mem0 collection: %s", collection_name)
    logger.info("mem0 qdrant path: %s", store_path)

    return {
        "llm": {
            "provider": "azure_openai",
            "config": {
                "model": settings.azure_openai_deployment,
                "temperature": 0.1,
                "max_tokens": 2000,
                "azure_kwargs": {
                    "azure_deployment": settings.azure_openai_deployment,
                    "api_version": settings.azure_openai_api_version,
                    "azure_endpoint": settings.azure_openai_endpoint,
                    "api_key": settings.azure_openai_api_key,
                },
            },
        },
        "embedder": embedder,
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": collection_name,
                "path": store_path,
            },
        },
    }


def _build_config() -> dict:
    provider = settings.embedding_provider.lower()
    defaults = _PROVIDER_DEFAULTS.get(provider, _PROVIDER_DEFAULTS["azure"])
    model = settings.embedding_model or defaults["model"]
    base_url = settings.embedding_base_url or defaults["base_url"]
    collection_name = _build_collection_name(provider, model)
    store_path = _build_store_path(provider, model)
    return _build_config_with(provider, model, base_url, collection_name, store_path)


def _build_legacy_config() -> dict:
    provider = settings.embedding_provider.lower()
    base_url = settings.embedding_base_url or _PROVIDER_DEFAULTS.get(provider, _PROVIDER_DEFAULTS["azure"])["base_url"]
    legacy_model = os.getenv("MEMORY_LEGACY_MODEL", "text-embedding-v4")
    legacy_collection = os.getenv("MEMORY_LEGACY_COLLECTION", "my_gpt_memories")
    legacy_path = os.getenv("MEMORY_LEGACY_PATH", "data/qdrant")
    logger.info("mem0 legacy collection: %s", legacy_collection)
    logger.info("mem0 legacy qdrant path: %s", legacy_path)
    return _build_config_with(provider, legacy_model, base_url, legacy_collection, legacy_path)


def get_memory() -> Memory:
    global _memory
    if _memory is None:
        config = _build_config()
        logger.info("mem0 初始化，embedding provider: %s", settings.embedding_provider)
        _memory = Memory.from_config(config)
    return _memory


def get_legacy_memory() -> Memory | None:
    global _legacy_memory
    # 默认严格隔离：一个模型一套存储，不跨模型读取
    enable_legacy = os.getenv("MEMORY_ENABLE_LEGACY_READ", "0").lower() in ("1", "true", "yes", "on")
    if not enable_legacy:
        return None
    if _legacy_memory is None:
        try:
            _legacy_memory = Memory.from_config(_build_legacy_config())
        except Exception as e:
            logger.warning("legacy memory 初始化失败: %s", e)
            return None
    return _legacy_memory


def _as_items(results: dict | list | None) -> list[dict]:
    if isinstance(results, dict):
        return results.get("results", []) or []
    return results or []


def _ensure_memory_table() -> None:
    global _table_ready
    if _table_ready:
        return
    conn = _db_connect()
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_memories (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            memory TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_memories_user_text ON user_memories(user_id, memory)"
    )
    conn.commit()
    conn.close()
    _table_ready = True


def _upsert_memory_rows(user_id: str, items: list[dict]) -> None:
    if not items:
        return
    _ensure_memory_table()
    conn = _db_connect()
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    for it in items:
        mem_text = (it.get("memory") or "").strip()
        if not mem_text:
            continue
        row_id = _stable_memory_row_id(user_id, mem_text)
        cur.execute(
            """
            INSERT INTO user_memories(id, user_id, memory, created_at)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(user_id, memory) DO UPDATE SET
              id=excluded.id,
              created_at=excluded.created_at
            """,
            (row_id, user_id, mem_text, now),
        )
    conn.commit()
    conn.close()


def _get_memory_rows(user_id: str, limit: int = 200) -> list[dict]:
    _ensure_memory_table()
    conn = _db_connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, memory, created_at
        FROM user_memories
        WHERE user_id = ?
        ORDER BY datetime(created_at) DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _search_memory_rows(user_id: str, query: str, limit: int = 5) -> list[dict]:
    _ensure_memory_table()
    q = (query or "").strip()
    if not q:
        return []
    conn = _db_connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT memory
        FROM user_memories
        WHERE user_id = ? AND memory LIKE ?
        ORDER BY datetime(created_at) DESC
        LIMIT ?
        """,
        (user_id, f"%{q}%", limit),
    )
    rows = [{"memory": r["memory"]} for r in cur.fetchall() if r["memory"]]
    conn.close()
    return rows


def _delete_memory_row(memory_id: str) -> None:
    _ensure_memory_table()
    conn = _db_connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM user_memories WHERE id = ?", (memory_id,))
    conn.commit()
    conn.close()


def _import_from_mem0_history(user_id: str, limit: int = 200) -> int:
    """
    一次性兼容迁移：
    当 user_memories 为空时，从 MEM0_DIR/history.db 回填最近的记忆文本。
    说明：mem0 history 表通常不含 user_id，这里仅在当前用户为空时作为兜底导入。
    """
    hist_db = os.path.join(_mem0_dir, "history.db")
    if not os.path.exists(hist_db):
        return 0
    try:
        conn = sqlite3.connect(hist_db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT new_memory, old_memory, event, created_at, is_deleted
            FROM history
            WHERE (is_deleted IS NULL OR is_deleted = 0)
            ORDER BY datetime(created_at) DESC
            LIMIT ?
            """,
            (max(limit * 3, 300),),
        )
        rows = cur.fetchall()
        conn.close()
    except Exception as e:
        logger.warning("import_from_history 失败: %s", e)
        return 0

    dedup: list[dict] = []
    seen: set[str] = set()
    for r in rows:
        text = (r["new_memory"] or r["old_memory"] or "").strip()
        if not text or text in seen:
            continue
        dedup.append({"id": "", "memory": text})
        seen.add(text)
        if len(dedup) >= limit:
            break
    if not dedup:
        return 0
    _upsert_memory_rows(user_id, dedup)
    logger.info("memory_import_from_history user_id=%s count=%d", user_id, len(dedup))
    return len(dedup)


def search_memories(query: str, user_id: str, limit: int = 5) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    max_total = limit + _RECENT_MEMORY_SUPPLEMENT
    sources: list[tuple[str, Memory | None]] = [("primary", get_memory()), ("legacy", get_legacy_memory())]
    for source_name, mem in sources:
        if mem is None:
            continue
        try:
            items = _as_items(mem.search(query, user_id=user_id, limit=limit))
            for r in items:
                text = r.get("memory", "")
                if text and text not in seen:
                    merged.append({"memory": text})
                    seen.add(text)
                if len(merged) >= limit:
                    break
            if len(merged) >= limit:
                break
        except Exception as e:
            logger.warning("search_memories 失败 [%s]: %s", source_name, e)
    if not merged:
        # 向量无果时：子串匹配 + 后面仍会补「最近记忆」
        fallback = _search_memory_rows(user_id, query, limit=limit)
        if fallback:
            logger.info("search_memories fallback_sql user_id=%s count=%d", user_id, len(fallback))
            for m in fallback:
                t = (m.get("memory") or "").strip()
                if t and t not in seen:
                    merged.append({"memory": t})
                    seen.add(t)
    # 与「当前问句」向量不相近的记忆（如身份类事实）仍应进上下文
    for row in _get_memory_rows(user_id, limit=_RECENT_MEMORY_POOL):
        text = (row.get("memory") or "").strip()
        if not text or text in seen:
            continue
        merged.append({"memory": text})
        seen.add(text)
        if len(merged) >= max_total:
            break
    if not merged:
        # 仅 mem0 有数据、向量失败且本地表空时
        for item in get_all_memories(user_id)[:max_total]:
            text = (item.get("memory") or "").strip()
            if text and text not in seen:
                merged.append({"memory": text})
                seen.add(text)
    return merged


def add_memories(messages: list[dict], user_id: str) -> None:
    try:
        logger.info("memory_add primary user_id=%s message_count=%d", user_id, len(messages))
        result = get_memory().add(messages, user_id=user_id)
        # 将 mem0 抽取结果同步到本地 user_memories，避免重启后 get_all 波动
        _upsert_memory_rows(user_id, _as_items(result))
        logger.info("memory_add primary success user_id=%s", user_id)
    except Exception as e:
        logger.warning("add_memories 失败: %s", e)
    dual_write = os.getenv("MEMORY_DUAL_WRITE_LEGACY", "0").lower() in ("1", "true", "yes", "on")
    if dual_write:
        legacy = get_legacy_memory()
        if legacy is not None:
            try:
                logger.info("memory_add legacy user_id=%s message_count=%d", user_id, len(messages))
                legacy.add(messages, user_id=user_id)
                logger.info("memory_add legacy success user_id=%s", user_id)
            except Exception as e:
                logger.warning("add_memories legacy 失败: %s", e)


def get_all_memories(user_id: str) -> list[dict]:
    # 以本地 user_memories 为主（稳定持久）
    rows = _get_memory_rows(user_id)
    if rows:
        return rows

    # 若本地为空，先尝试从 mem0 history 做一次兜底回填
    imported = _import_from_mem0_history(user_id, limit=200)
    if imported > 0:
        return _get_memory_rows(user_id)

    # 兼容老数据：若本地为空，再尝试从 mem0 拉取并回填一次
    merged: list[dict] = []
    seen: set[tuple[str, str]] = set()
    sources: list[tuple[str, Memory | None]] = [("primary", get_memory()), ("legacy", get_legacy_memory())]
    for source_name, mem in sources:
        if mem is None:
            continue
        try:
            items = _as_items(mem.get_all(user_id=user_id))
            for r in items:
                item = {
                    "id": r.get("id", ""),
                    "memory": r.get("memory", ""),
                    "created_at": r.get("created_at", ""),
                }
                key = (item["id"], item["memory"])
                if item["memory"] and key not in seen:
                    merged.append(item)
                    seen.add(key)
        except Exception as e:
            logger.warning("get_all_memories 失败 [%s]: %s", source_name, e)
    if merged:
        _upsert_memory_rows(user_id, merged)
    return merged


def delete_memory(memory_id: str) -> None:
    _delete_memory_row(memory_id)
    for source_name, mem in [("primary", get_memory()), ("legacy", get_legacy_memory())]:
        if mem is None:
            continue
        try:
            mem.delete(memory_id)
        except Exception as e:
            logger.warning("delete_memory 失败 [%s]: %s", source_name, e)
