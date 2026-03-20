import os
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

# 读取 backend/.env，确保独立网关进程能拿到配置
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(dotenv_path=os.path.join(_BACKEND_DIR, ".env"))

UPSTREAM_URL = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/multimodal-embedding/multimodal-embedding"
DEFAULT_UPSTREAM_MODEL = os.getenv("EMBEDDING_GATEWAY_UPSTREAM_MODEL", "tongyi-embedding-vision-plus")
UPSTREAM_API_KEY = os.getenv("EMBEDDING_API_KEY", "") or os.getenv("DASHSCOPE_API_KEY", "")
GATEWAY_API_KEY = os.getenv("EMBEDDING_GATEWAY_API_KEY", "")
REQUEST_TIMEOUT = float(os.getenv("EMBEDDING_GATEWAY_TIMEOUT", "20"))
TARGET_DIM = int(os.getenv("EMBEDDING_GATEWAY_TARGET_DIM", "1536"))


app = FastAPI(title="Embedding Gateway", version="0.1.0")


class EmbeddingRequest(BaseModel):
    input: str | list[str]
    model: str | None = None
    user: str | None = None
    encoding_format: str | None = None


def _extract_embedding(data: dict) -> list[float]:
    """
    容错解析 DashScope 返回结构：
    - output.embeddings[0].embedding
    - output.embedding
    - embeddings[0].embedding
    """
    output = data.get("output", {}) if isinstance(data, dict) else {}

    candidates: list[Any] = []
    if isinstance(output, dict):
        if isinstance(output.get("embeddings"), list) and output["embeddings"]:
            candidates.append(output["embeddings"][0])
        if isinstance(output.get("embedding"), list):
            candidates.append({"embedding": output["embedding"]})
    if isinstance(data.get("embeddings"), list) and data["embeddings"]:
        candidates.append(data["embeddings"][0])

    for item in candidates:
        emb = item.get("embedding") if isinstance(item, dict) else None
        if isinstance(emb, list) and emb:
            return emb
    raise ValueError("上游未返回 embedding 向量")


def _normalize_inputs(inp: str | list[str]) -> list[str]:
    if isinstance(inp, str):
        return [inp]
    return [x for x in inp if isinstance(x, str)]


def _normalize_dim(vec: list[float]) -> list[float]:
    """将上游向量归一化到固定维度，默认 1536（兼容 mem0/openai 预期）。"""
    if TARGET_DIM <= 0:
        return vec
    n = len(vec)
    if n == TARGET_DIM:
        return vec
    if n > TARGET_DIM:
        return vec[:TARGET_DIM]
    # 右侧补 0
    return vec + [0.0] * (TARGET_DIM - n)


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/v1/embeddings")
async def embeddings(payload: EmbeddingRequest, authorization: str | None = Header(default=None)):
    if GATEWAY_API_KEY:
        expected = f"Bearer {GATEWAY_API_KEY}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Unauthorized")

    if not UPSTREAM_API_KEY:
        raise HTTPException(status_code=500, detail="EMBEDDING_API_KEY 未配置")

    model = payload.model or DEFAULT_UPSTREAM_MODEL
    inputs = _normalize_inputs(payload.input)
    if not inputs:
        raise HTTPException(status_code=400, detail="input 不能为空")

    out_data: list[dict[str, Any]] = []
    prompt_tokens = 0

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        for idx, text in enumerate(inputs):
            upstream_body = {
                "model": model,
                "input": {"contents": [{"text": text}]},
            }
            resp = await client.post(
                UPSTREAM_URL,
                headers={
                    "Authorization": f"Bearer {UPSTREAM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=upstream_body,
            )
            if resp.status_code >= 400:
                detail = resp.text[:600]
                raise HTTPException(status_code=resp.status_code, detail=f"上游错误: {detail}")
            data = resp.json()
            try:
                emb = _extract_embedding(data)
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"解析上游向量失败: {e}") from e
            emb = _normalize_dim(emb)

            usage = data.get("usage") or {}
            prompt_tokens += int(usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0) or 0)
            out_data.append({"object": "embedding", "index": idx, "embedding": emb})

    return {
        "object": "list",
        "data": out_data,
        "model": model,
        "usage": {"prompt_tokens": prompt_tokens, "total_tokens": prompt_tokens},
    }
