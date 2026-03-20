import os
from dotenv import load_dotenv

# 提前加载 .env，确保 MEM0_DIR 在 mem0 模块导入前生效
load_dotenv()

# 确保 mem0 数据目录存在
_mem0_dir = os.environ.get("MEM0_DIR", os.path.join(os.path.expanduser("~"), ".mem0"))
os.makedirs(_mem0_dir, exist_ok=True)

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-06-01"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"

    tavily_api_key: str = ""

    # Embedding provider: "azure" | "dashscope" | "zhipu" | "ollama"
    embedding_provider: str = "azure"
    # 阿里云百炼 / 智谱 / 其他兼容 OpenAI 的 embedding key
    embedding_api_key: str = ""
    # dashscope base_url（默认已内置，可留空）
    embedding_base_url: str = ""
    # embedding 模型名，各 provider 默认值见 memory.py
    embedding_model: str = ""

    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_default_open_id: str = ""   # 填入后即可发消息给自己
    feishu_default_folder_token: str = ""  # 个人空间下某文件夹 token，文档将创建在此；不填则创建到应用默认空间
    feishu_wiki_node_token: str = ""  # 知识库页面 node token（URL 里 /wiki/ 后面的那串），配置后「写文档」将追加到该 Wiki 页
    feishu_wiki_base_url: str = ""  # 知识库访问域名，如 https://ocnxxel690ii.feishu.cn，返回的 Wiki 链接会用此域名；不填则用 open.feishu.cn（可能打不开）

    user_id: str = "default_user"

    # 注册人数上限；0 表示不限制。默认 1 与此前「仅开放一个账号」一致
    max_registered_users: int = 1

    db_path: str = "data/chat.db"
    # 与同步 sqlite3 共用 chat.db 时避免瞬时 database is locked
    sqlite_timeout_seconds: float = 30.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
