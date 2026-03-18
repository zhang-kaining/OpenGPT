"""
Skills & MCP 管理 API
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.mcp_manager import MCP_CONFIG_PATH, get_mcp_manager
from app.services.skill_manager import SKILLS_DIR, get_skill_manager

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ── Skills ────────────────────────────────────────────────────────────────────

@router.get("/skills")
async def list_skills():
    """列出所有 Skill 及其状态"""
    mgr = get_skill_manager()
    result = []
    for skill in mgr._skills.values():
        result.append({
            "name": skill.name,
            "description": skill.description,
            "enabled": skill.enabled,
            "tools": list(skill.tools.keys()),
        })
    return result


class SkillToggle(BaseModel):
    enabled: bool


@router.patch("/skills/{name}")
async def toggle_skill(name: str, body: SkillToggle):
    """启用/禁用某个 Skill（修改 SKILL.md frontmatter）"""
    mgr = get_skill_manager()
    skill = mgr.get(name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' 不存在")

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
