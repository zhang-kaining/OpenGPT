"""
Skills & MCP 管理 API
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.services import feishu as feishu_service
from app.services import web_search as web_search_service
from app.services.mcp_manager import MCP_CONFIG_PATH, get_mcp_manager
from app.services.skill_manager import SKILLS_DIR, get_skill_manager

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ── Skills ────────────────────────────────────────────────────────────────────

@router.get("/skills")
async def list_skills():
    """列出所有 Skill 及其状态"""
    s = get_settings()

    def _availability(name: str) -> tuple[bool, str]:
        if name in ("feishu", "feishu-write-doc"):
            if not (s.feishu_app_id or "").strip() or not (s.feishu_app_secret or "").strip():
                return False, "未配置飞书 App ID / App Secret"
        if name == "feishu":
            if not (s.feishu_default_open_id or "").strip():
                return False, "未配置飞书默认接收人 OpenID"
        if name == "feishu-write-doc":
            if not (s.feishu_wiki_node_token or "").strip():
                return False, "未配置飞书知识库节点 Token"
            if not (s.feishu_wiki_base_url or "").strip():
                return False, "未配置飞书知识库地址"
        if name == "web-search":
            if not (s.tavily_api_key or "").strip():
                return False, "未配置 Tavily 搜索密钥"
        return True, ""

    mgr = get_skill_manager()
    result = []
    for skill in mgr._skills.values():
        available, reason = _availability(skill.name)
        # 展示层按“可用且启用”计算，避免历史 enabled=true 造成“未配置但开关显示已开”
        display_enabled = bool(skill.enabled and available)
        result.append({
            "name": skill.name,
            "description": skill.description,
            "enabled": display_enabled,
            "tools": list(skill.tools.keys()),
            "available": available,
            "unavailable_reason": reason,
        })
    return result


class SkillToggle(BaseModel):
    enabled: bool


async def _precheck_skill_enable(name: str) -> None:
    """
    启用前预校验：
    - web-search: 验证 Tavily key 可正常调用
    - feishu / feishu-write-doc: 验证飞书 app_id/app_secret 可拿到 tenant token
    """
    s = get_settings()
    if name == "web-search":
        if not (s.tavily_api_key or "").strip():
            raise HTTPException(status_code=400, detail="启用失败：请先在系统配置中填写 Tavily 搜索密钥")
        try:
            # 最小探活，失败说明 key 无效或网络不可达
            web_search_service.search("ping", max_results=1)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"启用失败：Tavily 校验失败（{e}）") from e
        return

    if name in ("feishu", "feishu-write-doc"):
        if not (s.feishu_app_id or "").strip() or not (s.feishu_app_secret or "").strip():
            raise HTTPException(status_code=400, detail="启用失败：请先在系统配置中填写飞书 App ID 与 App Secret")
        if name == "feishu":
            if not (s.feishu_default_open_id or "").strip():
                raise HTTPException(status_code=400, detail="启用失败：请先填写飞书默认接收人 OpenID")
        if name == "feishu-write-doc":
            if not (s.feishu_wiki_node_token or "").strip():
                raise HTTPException(status_code=400, detail="启用失败：请先填写飞书知识库节点 Token")
            if not (s.feishu_wiki_base_url or "").strip():
                raise HTTPException(status_code=400, detail="启用失败：请先填写飞书知识库地址")
        try:
            await feishu_service.get_tenant_access_token()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"启用失败：飞书凭证校验失败（{e}）") from e


@router.patch("/skills/{name}")
async def toggle_skill(name: str, body: SkillToggle):
    """启用/禁用某个 Skill（修改 SKILL.md frontmatter）"""
    mgr = get_skill_manager()
    skill = mgr.get(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' 不存在")

    if body.enabled:
        await _precheck_skill_enable(name)

    skill_md = SKILLS_DIR / name / "SKILL.md"
    if not skill_md.exists():
        raise HTTPException(status_code=404, detail="SKILL.md 不存在")

    raw = skill_md.read_text(encoding="utf-8")
    if "enabled:" in raw:
        new_raw = "\n".join(
            f"enabled: {'true' if body.enabled else 'false'}" if line.strip().startswith("enabled:") else line
            for line in raw.splitlines()
        )
    else:
        # 插入到 frontmatter 末尾
        new_raw = raw.replace("---\n\n", f"enabled: {'true' if body.enabled else 'false'}\n---\n\n", 1)

    skill_md.write_text(new_raw, encoding="utf-8")

    # 重新加载
    mgr.load()
    return {"name": name, "enabled": body.enabled}


# ── MCP ───────────────────────────────────────────────────────────────────────

@router.get("/mcp")
async def get_mcp_config():
    """读取 mcp.json 内容"""
    if not MCP_CONFIG_PATH.exists():
        return {"mcpServers": {}}
    try:
        return json.loads(MCP_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class McpConfigBody(BaseModel):
    config: dict


@router.put("/mcp")
async def save_mcp_config(body: McpConfigBody):
    """保存 mcp.json 并重新加载 MCP 工具"""
    try:
        MCP_CONFIG_PATH.write_text(
            json.dumps(body.config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"写入失败: {e}")

    # 重置并重新加载
    from app.services import mcp_manager as _mcp_mod
    _mcp_mod._manager = None
    mgr = get_mcp_manager()
    await mgr.load()

    return {
        "servers": list(body.config.get("mcpServers", {}).keys()),
        "tools_loaded": len(mgr.tool_definitions),
    }


@router.get("/mcp/status")
async def get_mcp_status():
    """MCP 工具加载状态"""
    mgr = get_mcp_manager()
    return {
        "available": mgr.available,
        "tools": [t["function"]["name"] for t in mgr.tool_definitions],
    }
