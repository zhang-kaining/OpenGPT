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

    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_default_open_id: str = ""   # 填入后即可发消息给自己

    user_id: str = "default_user"

    db_path: str = "data/chat.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
