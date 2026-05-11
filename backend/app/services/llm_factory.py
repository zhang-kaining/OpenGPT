from __future__ import annotations

import json

import httpx
from openai import AsyncAzureOpenAI, AsyncOpenAI

from app.config import get_settings

# 模型对话（含流式）：单次请求读超时最长 5 分钟；连接仍保持较短以免挂死
LLM_HTTP_TIMEOUT = httpx.Timeout(300.0, connect=30.0)

_azure_clients: dict[str, AsyncAzureOpenAI] = {}
_openai_clients: dict[str, AsyncOpenAI] = {}


def reset_chat_clients() -> None:
    _azure_clients.clear()
    _openai_clients.clear()


def _parse_providers(s) -> list[dict]:
    try:
        providers = json.loads(s.llm_providers_json or "[]")
        return providers if isinstance(providers, list) else []
    except json.JSONDecodeError:
        return []


def _pick_provider(s, override_id: str | None) -> dict | None:
    providers = _parse_providers(s)
    provider_id = (override_id or s.active_llm_provider_id or "").strip()
    if provider_id:
        for provider in providers:
            if isinstance(provider, dict) and provider.get("id") == provider_id:
                return provider
    return providers[0] if providers else None


def resolve_llm(s, override_id: str | None = None) -> tuple[str, str, dict]:
    """
    返回 (kind, model, openai_extra)。
    kind 为 azure 时 model 为 deployment；openai 时 model 为兼容 API 的 model 名。
    openai_extra 仅 kind==openai 时有 base_url、api_key。

    须在设置中配置至少一条 llm_providers_json；不再在未配置时静默回退到全局 Azure。
    """
    if not _parse_providers(s):
        raise ValueError(
            "尚未配置任何模型提供方。请打开「设置 → 环境与模型」，至少添加一条提供方（OpenAI 兼容或 Azure）。"
        )

    provider = _pick_provider(s, override_id)
    if not provider:
        raise ValueError("无法解析当前选中的模型提供方，请检查 active_llm_provider_id 与列表中的 id 是否一致。")

    kind = str(provider.get("kind") or "").strip().lower()
    if kind == "openai":
        base_url = (provider.get("base_url") or "").strip().rstrip("/")
        api_key = (provider.get("api_key") or "").strip()
        model = (provider.get("model") or "gpt-4o-mini").strip()
        if not base_url:
            raise ValueError("当前 OpenAI 兼容提供方缺少 base_url，请在设置中补全后再试。")
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"
        return "openai", model, {"base_url": base_url, "api_key": api_key}

    if kind == "azure":
        deployment = (provider.get("deployment") or "").strip() or s.azure_openai_deployment
        if not deployment:
            raise ValueError("当前 Azure 提供方缺少 deployment，请在设置中补全后再试。")

        endpoint = (provider.get("endpoint") or "").strip() or s.azure_openai_endpoint
        api_version = (provider.get("api_version") or "").strip() or s.azure_openai_api_version
        api_key = (provider.get("api_key") or "").strip() or s.azure_openai_api_key
        if not endpoint:
            raise ValueError("当前 Azure 提供方缺少 endpoint，请在设置中补全后再试。")
        if not api_version:
            raise ValueError("当前 Azure 提供方缺少 api_version，请在设置中补全后再试。")
        if not api_key:
            raise ValueError("当前 Azure 提供方缺少 api_key，请在设置中补全后再试。")
        return "azure", deployment, {
            "endpoint": endpoint,
            "api_version": api_version,
            "api_key": api_key,
        }

    raise ValueError("模型提供方 kind 无效，仅支持 openai 或 azure。")


def get_llm_client(_settings, kind: str, openai_extra: dict):
    if kind == "azure":
        endpoint = str(openai_extra.get("endpoint") or "").strip()
        api_version = str(openai_extra.get("api_version") or "").strip()
        api_key = str(openai_extra.get("api_key") or "").strip()
        cache_key = f"{endpoint}|{api_version}|{api_key[:12]}"
        if cache_key not in _azure_clients:
            _azure_clients[cache_key] = AsyncAzureOpenAI(
                api_key=api_key,
                azure_endpoint=endpoint,
                api_version=api_version,
                timeout=LLM_HTTP_TIMEOUT,
            )
        return _azure_clients[cache_key]

    cache_key = f"{openai_extra.get('base_url', '')}|{openai_extra.get('api_key', '')[:12]}"
    if cache_key not in _openai_clients:
        _openai_clients[cache_key] = AsyncOpenAI(
            base_url=openai_extra["base_url"],
            api_key=openai_extra.get("api_key") or "EMPTY",
            timeout=LLM_HTTP_TIMEOUT,
        )
    return _openai_clients[cache_key]


def get_chat_client(llm_provider_id: str | None = None):
    """供笔记整理等单次调用：返回 (client, kind, model)。"""
    settings = get_settings()
    kind, model, extra = resolve_llm(settings, llm_provider_id)
    return get_llm_client(settings, kind, extra), kind, model
