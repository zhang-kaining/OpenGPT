"""运行时配置 API：读写 backend/data/settings.db（app_settings 表）；主应用不依赖 .env。"""

from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from openai import AzureOpenAI, OpenAI
from pydantic import BaseModel

from app.config import Settings, get_settings, reload_runtime_clients
from app.deps import get_current_user
from app.services import feishu as feishu_service
from app.services import runtime_config as rc

router = APIRouter(prefix="/api/settings", tags=["settings"])
logger = logging.getLogger(__name__)


def _is_secret_key(k: str) -> bool:
    lk = k.lower()
    return lk.endswith("_key") or lk.endswith("_secret") or "password" in lk


@router.get("/runtime")
async def get_runtime_settings(_user: dict = Depends(get_current_user)):
    s = get_settings()
    d = s.model_dump()
    for k, v in list(d.items()):
        if isinstance(v, str) and v.strip() and _is_secret_key(k):
            d[k] = "***"
    return d


class RuntimePutBody(BaseModel):
    values: dict[str, Any] = {}


class ProviderValidateBody(BaseModel):
    provider_type: str  # llm | embedding
    provider: dict[str, Any]
    globals: dict[str, Any] = {}


class CleanupEmbeddingStoreBody(BaseModel):
    provider: dict[str, Any]


def _parse_provider_json(raw: str, field_name: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"{field_name} JSON 无效: {e}") from e
    if not isinstance(parsed, list):
        raise HTTPException(status_code=400, detail=f"{field_name} 必须是 JSON 数组")
    out: list[dict[str, Any]] = []
    for i, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail=f"{field_name}[{i}] 必须是对象")
        pid = str(item.get("id", "")).strip()
        kind = str(item.get("kind", "")).strip().lower()
        if not pid:
            raise HTTPException(status_code=400, detail=f"{field_name}[{i}].id 不能为空")
        if kind not in ("openai", "azure"):
            raise HTTPException(status_code=400, detail=f"{field_name}[{i}].kind 仅支持 openai/azure")
        out.append(item)
    return out


@router.put("/runtime")
async def put_runtime_settings(body: RuntimePutBody, _user: dict = Depends(get_current_user)):
    allowed = set(Settings.model_fields.keys())
    patch: dict[str, Any] = {}
    for k, v in body.values.items():
        if k not in allowed:
            continue
        if v == "***":
            continue
        if v is None:
            patch[k] = None
            continue
        if isinstance(v, str) and not v.strip():
            patch[k] = None
            continue
        patch[k] = v

    if "db_path" in patch and patch["db_path"] is not None:
        dp = patch["db_path"]
        if not isinstance(dp, str) or not dp.strip():
            raise HTTPException(status_code=400, detail="db_path 不能为空")
        norm = dp.strip()
        if ".." in norm.replace("\\", "/"):
            raise HTTPException(status_code=400, detail="db_path 不能包含 ..")
        patch["db_path"] = norm

    if "sqlite_timeout_seconds" in patch and patch["sqlite_timeout_seconds"] is not None:
        try:
            t = float(patch["sqlite_timeout_seconds"])
        except (TypeError, ValueError) as e:
            raise HTTPException(status_code=400, detail="sqlite_timeout_seconds 须为正数") from e
        if t <= 0:
            raise HTTPException(status_code=400, detail="sqlite_timeout_seconds 须为正数")
        patch["sqlite_timeout_seconds"] = t

    raw_json = patch.get("llm_providers_json")
    if isinstance(raw_json, str) and raw_json.strip():
        _parse_provider_json(raw_json, "llm_providers_json")
    emb_json = patch.get("embedding_providers_json")
    if isinstance(emb_json, str) and emb_json.strip():
        _parse_provider_json(emb_json, "embedding_providers_json")
    rc.update_raw(patch)
    reload_runtime_clients()
    return {"ok": True}


def _must_str(v: Any) -> str:
    return str(v or "").strip()


def _probe_llm(provider: dict[str, Any], g: dict[str, Any]) -> None:
    kind = _must_str(provider.get("kind")).lower()
    if kind == "openai":
        base_url = _must_str(provider.get("base_url"))
        api_key = _must_str(provider.get("api_key"))
        model = _must_str(provider.get("model")) or "gpt-4o-mini"
        if not base_url:
            raise ValueError("OpenAI 兼容缺少 base_url")
        if not base_url.endswith("/v1"):
            base_url = f"{base_url.rstrip('/')}/v1"
        client = OpenAI(base_url=base_url, api_key=api_key or "EMPTY")
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
        )
        return
    if kind == "azure":
        endpoint = _must_str(provider.get("endpoint")) or _must_str(g.get("azure_openai_endpoint"))
        api_version = _must_str(provider.get("api_version")) or _must_str(g.get("azure_openai_api_version")) or "2024-06-01"
        api_key = _must_str(provider.get("api_key")) or _must_str(g.get("azure_openai_api_key"))
        deployment = _must_str(provider.get("deployment")) or _must_str(g.get("azure_openai_deployment"))
        if not endpoint:
            raise ValueError("Azure 缺少 endpoint")
        if not api_key:
            raise ValueError("Azure 缺少 api_key")
        if not deployment:
            raise ValueError("Azure 缺少 deployment")
        client = AzureOpenAI(api_key=api_key, azure_endpoint=endpoint, api_version=api_version)
        client.chat.completions.create(
            model=deployment,
            messages=[{"role": "user", "content": "ping"}],
        )
        return
    raise ValueError("kind 仅支持 openai/azure")


def _probe_embedding(provider: dict[str, Any], g: dict[str, Any]) -> None:
    kind = _must_str(provider.get("kind")).lower()
    dim_raw = provider.get("dimensions", provider.get("embedding_dims"))
    dims = int(dim_raw) if str(dim_raw or "").strip() else None
    if kind == "openai":
        base_url = _must_str(provider.get("base_url"))
        api_key = _must_str(provider.get("api_key"))
        model = _must_str(provider.get("model")) or "text-embedding-3-small"
        if not base_url:
            raise ValueError("OpenAI 兼容缺少 base_url")
        if not base_url.endswith("/v1"):
            base_url = f"{base_url.rstrip('/')}/v1"
        client = OpenAI(base_url=base_url, api_key=api_key or "EMPTY")
        kwargs: dict[str, Any] = {"model": model, "input": "ping"}
        if dims and dims > 0:
            kwargs["dimensions"] = dims
        client.embeddings.create(**kwargs)
        return
    if kind == "azure":
        endpoint = _must_str(provider.get("endpoint")) or _must_str(g.get("azure_openai_endpoint"))
        api_version = _must_str(provider.get("api_version")) or _must_str(g.get("azure_openai_api_version")) or "2024-06-01"
        api_key = _must_str(provider.get("api_key")) or _must_str(g.get("azure_openai_api_key"))
        deployment = _must_str(provider.get("deployment")) or _must_str(g.get("azure_openai_embedding_deployment"))
        if not endpoint:
            raise ValueError("Azure 缺少 endpoint")
        if not api_key:
            raise ValueError("Azure 缺少 api_key")
        if not deployment:
            raise ValueError("Azure 缺少 deployment")
        client = AzureOpenAI(api_key=api_key, azure_endpoint=endpoint, api_version=api_version)
        kwargs = {"model": deployment, "input": "ping"}
        if dims and dims > 0:
            kwargs["dimensions"] = dims
        client.embeddings.create(**kwargs)
        return
    raise ValueError("kind 仅支持 openai/azure")


@router.post("/validate-provider")
async def validate_provider(body: ProviderValidateBody, _user: dict = Depends(get_current_user)):
    ptype = _must_str(body.provider_type).lower()
    provider = body.provider if isinstance(body.provider, dict) else {}
    if not provider:
        raise HTTPException(status_code=400, detail="provider 不能为空")
    try:
        if ptype == "llm":
            _probe_llm(provider, body.globals)
        elif ptype == "embedding":
            _probe_embedding(provider, body.globals)
        else:
            raise HTTPException(status_code=400, detail="provider_type 仅支持 llm/embedding")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"连通性校验失败: {e}") from e
    return {"ok": True}


def _embedding_model_from_provider(p: dict[str, Any], s: Settings) -> str:
    kind = _must_str(p.get("kind")).lower()
    if kind == "azure":
        return _must_str(p.get("deployment")) or _must_str(s.azure_openai_embedding_deployment) or "text-embedding-3-small"
    return _must_str(p.get("model")) or "text-embedding-3-small"


def _embedding_dim_tag_from_provider(p: dict[str, Any]) -> str:
    raw = p.get("dimensions", p.get("embedding_dims"))
    try:
        if raw not in (None, ""):
            v = int(raw)
            if v > 0:
                return f"d{v}"
    except (TypeError, ValueError):
        pass
    return "dauto"


def _sanitize_token(v: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", (v or "")).strip("_").lower()


@router.post("/cleanup-embedding-store")
async def cleanup_embedding_store(body: CleanupEmbeddingStoreBody, _user: dict = Depends(get_current_user)):
    p = body.provider if isinstance(body.provider, dict) else {}
    provider_id = _must_str(p.get("id"))
    if not provider_id:
        raise HTTPException(status_code=400, detail="provider.id 不能为空")
    s = get_settings()
    model = _embedding_model_from_provider(p, s)
    dim_tag = _embedding_dim_tag_from_provider(p)
    ns = f"{_sanitize_token(provider_id)}_{_sanitize_token(model)}_{_sanitize_token(dim_tag)}"[:80]
    rel_path = f"data/qdrant_{ns}"
    backend_root = Path(__file__).resolve().parents[2]
    target = (backend_root / rel_path).resolve()
    data_root = (backend_root / "data").resolve()
    if data_root not in target.parents:
        raise HTTPException(status_code=400, detail="非法目录")
    if not target.name.startswith("qdrant_"):
        raise HTTPException(status_code=400, detail="仅允许清理 qdrant_* 目录")
    if target.exists():
        shutil.rmtree(target)
        return {"ok": True, "deleted": True, "path": rel_path}
    return {"ok": True, "deleted": False, "path": rel_path}


@router.get("/llm-catalog")
async def llm_catalog(_user: dict = Depends(get_current_user)):
    """对话页下拉：模型提供方列表（密钥已打码）。"""
    s = get_settings()
    try:
        provs = json.loads(s.llm_providers_json or "[]")
        if not isinstance(provs, list):
            provs = []
    except json.JSONDecodeError:
        provs = []
    out: list[dict] = []
    for p in provs:
        if not isinstance(p, dict):
            continue
        q = dict(p)
        ak = q.get("api_key")
        if isinstance(ak, str) and ak.strip():
            q["api_key"] = "***"
        out.append(q)
    # 不在此伪造默认项：未配置 llm_providers_json 时列表为空，与「未添加提供方」一致
    return {"providers": out, "active_id": s.active_llm_provider_id}


@router.get("/embedding-catalog")
async def embedding_catalog(_user: dict = Depends(get_current_user)):
    """向量页下拉：embedding 提供方列表（密钥已打码）。"""
    s = get_settings()
    try:
        provs = json.loads(s.embedding_providers_json or "[]")
        if not isinstance(provs, list):
            provs = []
    except json.JSONDecodeError:
        provs = []
    out: list[dict] = []
    for p in provs:
        if not isinstance(p, dict):
            continue
        q = dict(p)
        ak = q.get("api_key")
        if isinstance(ak, str) and ak.strip():
            q["api_key"] = "***"
        out.append(q)
    return {"providers": out, "active_id": s.active_embedding_provider_id}


@router.get("/feishu-recipients")
async def feishu_recipients(_user: dict = Depends(get_current_user)):
    s = get_settings()
    if not (s.feishu_app_id or "").strip() or not (s.feishu_app_secret or "").strip():
        raise HTTPException(status_code=400, detail="请先在系统配置中填写飞书 App ID 与 App Secret")
    sec = (s.feishu_app_secret or "").strip()
    sec_masked = (sec[:3] + "***" + sec[-3:]) if len(sec) >= 7 else "***"
    logger.info(
        "feishu_recipients load with app_id=%s app_secret=%s default_open_id=%s",
        (s.feishu_app_id or "").strip(),
        sec_masked,
        (s.feishu_default_open_id or "").strip(),
    )
    try:
        users = await feishu_service.list_visible_users(limit=200)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"拉取飞书可见成员失败: {e}") from e
    return {"items": users}
