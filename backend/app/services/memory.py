import logging
import os
from dotenv import load_dotenv

# mem0 在模块级别读取 MEM0_DIR，必须在导入前设置
load_dotenv()
_mem0_dir = os.environ.get("MEM0_DIR", os.path.join(os.path.expanduser("~"), ".mem0"))
os.makedirs(_mem0_dir, exist_ok=True)

from mem0 import Memory
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_memory: Memory | None = None

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


def _build_config() -> dict:
    provider = settings.embedding_provider.lower()
    defaults = _PROVIDER_DEFAULTS.get(provider, _PROVIDER_DEFAULTS["azure"])

    model = settings.embedding_model or defaults["model"]
    base_url = settings.embedding_base_url or defaults["base_url"]

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
                "collection_name": "my_gpt_memories",
                "path": "data/qdrant",
            },
        },
    }


def get_memory() -> Memory:
    global _memory
    if _memory is None:
        config = _build_config()
        logger.info("mem0 初始化，embedding provider: %s", settings.embedding_provider)
        _memory = Memory.from_config(config)
    return _memory


def search_memories(query: str, user_id: str, limit: int = 5) -> list[dict]:
    try:
        results = get_memory().search(query, user_id=user_id, limit=limit)
        items = results.get("results", []) if isinstance(results, dict) else (results or [])
        return [{"memory": r["memory"]} for r in items if r.get("memory")]
    except Exception as e:
        logger.warning("search_memories 失败: %s", e)
        return []


def add_memories(messages: list[dict], user_id: str) -> None:
    try:
        get_memory().add(messages, user_id=user_id)
    except Exception as e:
        logger.warning("add_memories 失败: %s", e)


def get_all_memories(user_id: str) -> list[dict]:
    try:
        results = get_memory().get_all(user_id=user_id)
        items = results.get("results", []) if isinstance(results, dict) else (results or [])
        return [
            {"id": r.get("id", ""), "memory": r.get("memory", ""), "created_at": r.get("created_at", "")}
            for r in items
        ]
    except Exception as e:
        logger.warning("get_all_memories 失败: %s", e)
        return []


def delete_memory(memory_id: str) -> None:
    try:
        get_memory().delete(memory_id)
    except Exception as e:
        logger.warning("delete_memory 失败: %s", e)
