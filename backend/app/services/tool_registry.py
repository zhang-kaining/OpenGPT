from __future__ import annotations

from app.config import get_settings
from app.services import feishu as feishu_service
from app.services.mcp_manager import get_mcp_manager
from app.services.skill_manager import get_skill_manager


def build_initial_tools() -> list[dict]:
    """构建每轮对话起始可见的工具列表。"""
    settings = get_settings()
    skill_mgr = get_skill_manager()
    mcp_mgr = get_mcp_manager()
    tools: list[dict] = []

    if settings.feishu_app_id and settings.feishu_app_secret:
        tools.append(feishu_service.TOOL_DEFINITION)

    tools.extend(skill_mgr.get_all_tool_definitions())

    if mcp_mgr.available:
        tools.extend(mcp_mgr.tool_definitions)

    pure_skills = [skill for skill in skill_mgr.enabled_skills if not skill.tools]
    if pure_skills:
        tools.append(skill_mgr.get_skill_detail_definition)

    return tools
