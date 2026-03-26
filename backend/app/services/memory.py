import hashlib
import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone

from mem0 import Memory
from app.config import get_settings
from app.services import azure_openai as oai_service
from app.services import runtime_config as rc

logger = logging.getLogger(__name__)


def _resolved_mem0_dir() -> str:
    get_settings()
    return os.environ["MEM0_DIR"]


def _memory_flag_truthy(raw: str) -> bool:
    return (raw or "").strip().lower() in ("1", "true", "yes", "on")

_memory: Memory | None = None
_legacy_memory: Memory | None = None
_table_ready = False
_SQLITE_BUSY_MS = 30000
# 对话检索除向量外，追加最近几条本地记忆，避免「我是谁」等与记忆正文 embedding 不相近时搜不到
_RECENT_MEMORY_SUPPLEMENT = 3
_RECENT_MEMORY_POOL = 40


def reset_memory_clients() -> None:
    global _memory, _legacy_memory
    _memory = None
    _legacy_memory = None


def _db_connect() -> sqlite3.Connection:
    """与 aiosqlite 共用 chat.db 时减少锁竞争。"""
    conn = sqlite3.connect(get_settings().db_path, timeout=_SQLITE_BUSY_MS / 1000.0)
    conn.execute(f"PRAGMA busy_timeout={_SQLITE_BUSY_MS}")
    return conn


def _stable_memory_row_id(user_id: str, memory_text: str) -> str:
    """主键：勿用 mem0 返回的 '0'/'1'，多轮请求会重复导致 UNIQUE 冲突。"""
    h = hashlib.sha256(f"{user_id}\n{memory_text}".encode("utf-8")).hexdigest()
    return f"um_{h}"

def _parse_embedding_providers(s) -> list[dict]:
    try:
        v = json.loads(s.embedding_providers_json or "[]")
        return v if isinstance(v, list) else []
    except json.JSONDecodeError:
        return []


def _legacy_embedding_to_provider(s) -> dict:
    legacy_provider = (s.embedding_provider or "").strip().lower()
    kind = "azure" if legacy_provider == "azure" else "openai"
    out: dict[str, object] = {
        "id": f"{kind}-default",
        "name": "Embedding 默认提供方",
        "kind": kind,
    }
    if kind == "azure":
        out["deployment"] = (s.embedding_model or s.azure_openai_embedding_deployment or "text-embedding-3-small").strip()
        if s.azure_openai_endpoint:
            out["endpoint"] = s.azure_openai_endpoint
        if s.azure_openai_api_version:
            out["api_version"] = s.azure_openai_api_version
        if s.embedding_api_key:
            out["api_key"] = s.embedding_api_key
        elif s.azure_openai_api_key:
            out["api_key"] = s.azure_openai_api_key
    else:
        out["model"] = (s.embedding_model or "text-embedding-3-small").strip()
        if s.embedding_base_url:
            out["base_url"] = s.embedding_base_url
        if s.embedding_api_key:
            out["api_key"] = s.embedding_api_key
    return out


def _migrate_embedding_providers_if_needed(s) -> list[dict]:
    provs = _parse_embedding_providers(s)
    if provs:
        return provs
    has_legacy = bool(
        (s.embedding_provider or "").strip()
        or (s.embedding_base_url or "").strip()
        or (s.embedding_api_key or "").strip()
        or (s.embedding_model or "").strip()
    )
    if not has_legacy:
        return []
    item = _legacy_embedding_to_provider(s)
    try:
        rc.update_raw(
            {
                "embedding_providers_json": json.dumps([item], ensure_ascii=False),
                "active_embedding_provider_id": str(item.get("id", "")),
            }
        )
    except Exception as e:
        logger.warning("embedding 单配置迁移失败: %s", e)
    return [item]


def _pick_embedding_provider(s) -> dict:
    provs = _migrate_embedding_providers_if_needed(s)
    pid = (s.active_embedding_provider_id or "").strip()
    if pid:
        for p in provs:
            if isinstance(p, dict) and str(p.get("id", "")).strip() == pid:
                return p
    for p in provs:
        if isinstance(p, dict):
            kind = str(p.get("kind", "")).strip().lower()
            if kind in ("openai", "azure"):
                return p
    # 兜底仍可用：无配置时回退到默认 azure
    return {
        "id": "azure-default",
        "name": "Azure Embedding",
        "kind": "azure",
        "deployment": s.azure_openai_embedding_deployment or "text-embedding-3-small",
        "endpoint": s.azure_openai_endpoint,
        "api_version": s.azure_openai_api_version,
    }


def _normalized_dim_tag(provider_cfg: dict) -> str:
    raw = provider_cfg.get("dimensions", provider_cfg.get("embedding_dims"))
    try:
        if raw not in (None, ""):
            v = int(raw)
            if v > 0:
                return f"d{v}"
    except (TypeError, ValueError):
        pass
    return "dauto"


def _build_collection_name(provider: str, model: str, dim_tag: str) -> str:
    """
    按 provider + model 生成稳定 collection 名，避免不同向量维度写到同一集合。
    例如:
      OpenGPT_memories_dashscope_text_embedding_v4
      OpenGPT_memories_dashscope_multimodal_embedding_v1
    """
    p = re.sub(r"[^a-zA-Z0-9]+", "_", (provider or "unknown")).strip("_").lower()
    m = re.sub(r"[^a-zA-Z0-9]+", "_", (model or "default")).strip("_").lower()
    d = re.sub(r"[^a-zA-Z0-9]+", "_", (dim_tag or "dauto")).strip("_").lower()
    name = f"OpenGPT_memories_{p}_{m}_{d}"
    return name[:120]


def _build_store_path(provider: str, model: str, dim_tag: str) -> str:
    """
    按 provider + model 隔离 qdrant 本地存储目录，避免 mem0 内部集合（如 mem0migrations）
    在不同向量维度之间冲突。
    基路径跟随 db_path 所在目录，确保桌面版数据落到 userData。
    """
    p = re.sub(r"[^a-zA-Z0-9]+", "_", (provider or "unknown")).strip("_").lower()
    m = re.sub(r"[^a-zA-Z0-9]+", "_", (model or "default")).strip("_").lower()
    d = re.sub(r"[^a-zA-Z0-9]+", "_", (dim_tag or "dauto")).strip("_").lower()
    ns = f"{p}_{m}_{d}"[:80]
    db_dir = os.path.dirname(os.environ.get("DB_PATH", "").strip() or "data/chat.db")
    return os.path.join(db_dir, f"qdrant_{ns}")


def _build_mem0_llm_config(s) -> dict:
    """
    mem0 的事实抽取 LLM 与对话模型保持一致，避免只配置了 provider
    但未填全局 Azure 时初始化失败。
    """
    kind, model_name, extra = oai_service.resolve_llm(s)
    if kind == "openai":
        cfg: dict[str, object] = {
            "model": model_name,
            "temperature": 0.1,
            "max_tokens": 2000,
            "api_key": str(extra.get("api_key") or ""),
        }
        base = str(extra.get("base_url") or "").strip()
        if base:
            cfg["openai_base_url"] = base
        return {"provider": "openai", "config": cfg}
    return {
        "provider": "azure_openai",
        "config": {
            "model": model_name,
            "temperature": 0.1,
            "max_tokens": 2000,
            "azure_kwargs": {
                "azure_deployment": model_name,
                "api_version": str(extra.get("api_version") or s.azure_openai_api_version),
                "azure_endpoint": str(extra.get("endpoint") or s.azure_openai_endpoint),
                "api_key": str(extra.get("api_key") or s.azure_openai_api_key),
            },
        },
    }


def _build_config_with(provider_kind: str, model: str, provider_cfg: dict, collection_name: str, store_path: str, s) -> dict:
    dimensions_raw = provider_cfg.get("dimensions")
    dimensions: int | None = None
    try:
        if dimensions_raw not in (None, ""):
            dimensions = int(dimensions_raw)
    except (TypeError, ValueError):
        dimensions = None

    if provider_kind == "azure":
        endpoint = str(provider_cfg.get("endpoint") or s.azure_openai_endpoint).strip()
        api_version = str(provider_cfg.get("api_version") or s.azure_openai_api_version).strip()
        api_key = str(provider_cfg.get("api_key") or s.azure_openai_api_key).strip()
        embedder = {
            "provider": "azure_openai",
            "config": {
                "model": model,
                "azure_kwargs": {
                    "azure_deployment": model,
                    "api_version": api_version,
                    "azure_endpoint": endpoint,
                    "api_key": api_key,
                },
            },
        }
    else:
        api_key = str(provider_cfg.get("api_key") or s.embedding_api_key).strip()
        base_url = str(provider_cfg.get("base_url") or "").strip().rstrip("/")
        embedder_cfg: dict = {"model": model, "api_key": api_key}
        if base_url:
            if not base_url.endswith("/v1"):
                base_url = f"{base_url}/v1"
            embedder_cfg["openai_base_url"] = base_url
        if dimensions and dimensions > 0:
            embedder_cfg["embedding_dims"] = dimensions
        embedder = {"provider": "openai", "config": embedder_cfg}

    logger.info("mem0 collection: %s", collection_name)
    logger.info("mem0 qdrant path: %s", store_path)

    return {
        "llm": _build_mem0_llm_config(s),
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
    s = get_settings()
    p = _pick_embedding_provider(s)
    kind = str(p.get("kind", "")).strip().lower()
    if kind not in ("openai", "azure"):
        kind = "azure"
    model = (
        str(p.get("deployment") or "").strip()
        if kind == "azure"
        else str(p.get("model") or "").strip()
    )
    if not model:
        model = s.azure_openai_embedding_deployment if kind == "azure" else "text-embedding-3-small"
    provider_tag = str(p.get("id") or kind).strip() or kind
    dim_tag = _normalized_dim_tag(p)
    collection_name = _build_collection_name(provider_tag, model, dim_tag)
    store_path = _build_store_path(provider_tag, model, dim_tag)
    return _build_config_with(kind, model, p, collection_name, store_path, s)


def _build_legacy_config() -> dict:
    s = get_settings()
    p = _pick_embedding_provider(s)
    kind = str(p.get("kind", "")).strip().lower()
    if kind not in ("openai", "azure"):
        kind = "azure"
    legacy_model = s.memory_legacy_model or "text-embedding-v4"
    legacy_collection = s.memory_legacy_collection or "OpenGPT_memories"
    legacy_path = s.memory_legacy_path or "data/qdrant"
    logger.info("mem0 legacy collection: %s", legacy_collection)
    logger.info("mem0 legacy qdrant path: %s", legacy_path)
    return _build_config_with(kind, legacy_model, p, legacy_collection, legacy_path, s)


def get_memory() -> Memory:
    global _memory
    if _memory is None:
        config = _build_config()
        logger.info("mem0 初始化，active embedding provider: %s", get_settings().active_embedding_provider_id or "(auto)")
        _memory = Memory.from_config(config)
    return _memory


def get_legacy_memory() -> Memory | None:
    global _legacy_memory
    # 默认严格隔离：一个模型一套存储，不跨模型读取
    enable_legacy = _memory_flag_truthy(get_settings().memory_enable_legacy_read)
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
    hist_db = os.path.join(_resolved_mem0_dir(), "history.db")
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
    dual_write = _memory_flag_truthy(get_settings().memory_dual_write_legacy)
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
