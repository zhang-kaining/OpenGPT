from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

from app.services import feishu as feishu_service
from app.services import web_search as search_service
from app.services.mcp_manager import get_mcp_manager
from app.services.skill_manager import get_skill_manager
from app.services.tool_result_normalizer import (
    build_mcp_tool_start_events,
    format_search_results,
    normalize_mcp_tool_result,
)

logger = logging.getLogger(__name__)


@dataclass
class ToolExecutionResult:
    tool_call_id: str
    content: str
    sse_events: list[dict]
    new_tool_defs: list[dict]


async def dispatch_tool_calls(
    tool_calls: list[dict],
    all_citations: list[dict],
) -> list[ToolExecutionResult]:
    tasks = [
        execute_tool_call(tool_call, all_citations)
        for tool_call in tool_calls
    ]
    return await asyncio.gather(*tasks)


async def execute_tool_call(
    tool_call: dict,
    all_citations: list[dict],
) -> ToolExecutionResult:
    """
    执行单个工具调用。
    返回标准化后的工具结果、SSE 事件和动态注入工具定义。
    """
    tool_call_id = tool_call["id"]
    function_name = tool_call["function"]["name"]
    sse_events: list[dict] = []
    new_tool_defs: list[dict] = []

    try:
        args = json.loads(tool_call["function"]["arguments"])
    except Exception:
        args = {}

    skill_mgr = get_skill_manager()
    mcp_mgr = get_mcp_manager()

    if function_name == "web_search":
        query = args.get("query", "")
        sse_events.append({"type": "searching", "query": query})
        results = await asyncio.get_event_loop().run_in_executor(
            None,
            search_service.search,
            query,
        )
        offset = len(all_citations)
        for result in results:
            result["index"] = offset + result["index"]
        all_citations.extend(results)
        sse_events.append({"type": "search_results", "results": results})
        content = format_search_results(results)
        return ToolExecutionResult(tool_call_id, content, sse_events, new_tool_defs)

    if function_name == "feishu_send_message":
        content = args.get("content", "")
        sse_events.append({"type": "tool_call", "name": function_name, "status": "sending"})
        result = await feishu_service.send_message(content)
        tool_content = (
            "消息已成功发送到飞书。"
            if result["success"]
            else f"发送失败：{result.get('error', '未知错误')}"
        )
        return ToolExecutionResult(tool_call_id, tool_content, sse_events, new_tool_defs)

    if function_name == "get_skill_detail":
        skill_name = args.get("skill_name", "")
        skill = skill_mgr.get(skill_name)
        if skill and skill.enabled:
            new_tool_defs = [tool.definition for tool in skill.tools.values()]
            sse_events.append({"type": "tool_call", "name": "get_skill_detail", "status": skill_name})
            return ToolExecutionResult(tool_call_id, skill.detail, sse_events, new_tool_defs)

        available = [skill.name for skill in skill_mgr.enabled_skills]
        tool_content = f"未找到技能 '{skill_name}'，可用技能：{available}"
        return ToolExecutionResult(tool_call_id, tool_content, sse_events, new_tool_defs)

    skill_tool = skill_mgr.find_tool(function_name)
    if skill_tool is not None:
        sse_events.append({"type": "tool_call", "name": function_name, "status": "running"})
        try:
            if asyncio.iscoroutinefunction(skill_tool.function):
                result = await skill_tool.function(**args)
            else:
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: skill_tool.function(**args),
                )
            return ToolExecutionResult(tool_call_id, str(result), sse_events, new_tool_defs)
        except Exception as exc:
            logger.error("Skill 工具执行失败 [%s]: %s", function_name, exc)
            return ToolExecutionResult(tool_call_id, f"工具执行失败: {exc}", sse_events, new_tool_defs)

    if mcp_mgr.has_tool(function_name):
        sse_events.extend(build_mcp_tool_start_events(function_name, args))
        raw_content = await mcp_mgr.call_tool(function_name, args)
        normalized = normalize_mcp_tool_result(
            function_name,
            raw_content,
            citation_offset=len(all_citations),
        )
        all_citations.extend(normalized.citations)
        sse_events.extend(normalized.sse_events)
        return ToolExecutionResult(
            tool_call_id,
            normalized.content,
            sse_events,
            new_tool_defs,
        )

    logger.warning("未知工具调用: %s", function_name)
    return ToolExecutionResult(tool_call_id, f"未找到工具 '{function_name}'", sse_events, new_tool_defs)
