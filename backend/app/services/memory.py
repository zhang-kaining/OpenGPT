import os
from dotenv import load_dotenv

# 必须在 mem0 导入前设置 MEM0_DIR，因为 mem0 在模块级别读取该变量
load_dotenv()
_mem0_dir = os.environ.get("MEM0_DIR", os.path.join(os.path.expanduser("~"), ".mem0"))
os.makedirs(_mem0_dir, exist_ok=True)

from mem0 import Memory
from app.config import get_settings
from typing import Optional

settings = get_settings()

_memory: Memory | None = None


def get_memory() -> Memory:
    global _memory
    if _memory is None:
        config = {
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
                    }
                }
            },
            "embedder": {
                "provider": "azure_openai",
                "config": {
                    "model": settings.azure_openai_embedding_deployment,
                    "azure_kwargs": {
                        "azure_deployment": settings.azure_openai_embedding_deployment,
                        "api_version": settings.azure_openai_api_version,
                        "azure_endpoint": settings.azure_openai_endpoint,
                        "api_key": settings.azure_openai_api_key,
                    }
                }
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "my_gpt_memories",
                    "path": "data/qdrant",
                }
            }
        }
        _memory = Memory.from_config(config)
    return _memory


def search_memories(query: str, user_id: str, limit: int = 5) -> list[dict]:
    try:
        mem = get_memory()
        results = mem.search(query, user_id=user_id, limit=limit)
        if isinstance(results, dict):
            items = results.get("results", [])
        else:
            items = results or []
        return [{"memory": r.get("memory", "")} for r in items if r.get("memory")]
    except Exception:
        return []


def add_memories(messages: list[dict], user_id: str):
    try:
        mem = get_memory()
        mem.add(messages, user_id=user_id)
    except Exception:
        pass


def get_all_memories(user_id: str) -> list[dict]:
    try:
        mem = get_memory()
        results = mem.get_all(user_id=user_id)
        if isinstance(results, dict):
            items = results.get("results", [])
        else:
            items = results or []
        return [
            {
                "id": r.get("id", ""),
                "memory": r.get("memory", ""),
                "created_at": r.get("created_at", "")
            }
            for r in items
        ]
    except Exception:
        return []


def delete_memory(memory_id: str):
    try:
        mem = get_memory()
        mem.delete(memory_id)
    except Exception:
        pass
