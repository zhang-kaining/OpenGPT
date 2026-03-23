"""
Azure OpenAI 流式对话核心
=========================
工具调度优先级：
  1. 内置工具（web_search、feishu_send_message）
  2. Skill tool.py 注册的工具
  3. MCP 工具
  4. get_skill_detail（按需加载 Skill 详细指令）
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

import httpx
from openai import AsyncAzureOpenAI, AsyncOpenAI

# 模型对话（含流式）：单次请求读超时最长 5 分钟；连接仍保持较短以免挂死
LLM_HTTP_TIMEOUT = httpx.Timeout(300.0, connect=30.0)

from app.config import get_settings
from app.services import feishu as feishu_service
from app.services import web_search as search_service
from app.services.mcp_manager import get_mcp_manager
from app.services.skill_manager import get_skill_manager

logger = logging.getLogger(__name__)

_azure_clients: dict[str, AsyncAzureOpenAI] = {}
_openai_clients: dict[str, AsyncOpenAI] = {}


def reset_chat_clients() -> None:
    _azure_clients.clear()
    _openai_clients.clear()


def _parse_providers(s) -> list[dict]:
    try:
        v = json.loads(s.llm_providers_json or "[]")
        return v if isinstance(v, list) else []
    except json.JSONDecodeError:
        return []


def _pick_provider(s, override_id: str | None) -> dict | None:
    provs = _parse_providers(s)
    pid = (override_id or s.active_llm_provider_id or "").strip()
    if pid:
        for p in provs:
            if isinstance(p, dict) and p.get("id") == pid:
                return p
    return provs[0] if provs else None


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
    p = _pick_provider(s, override_id)
    if not p:
        raise ValueError("无法解析当前选中的模型提供方，请检查 active_llm_provider_id 与列表中的 id 是否一致。")
    kind = str(p.get("kind") or "").strip().lower()
    if kind == "openai":
        base = (p.get("base_url") or "").strip().rstrip("/")
        key = (p.get("api_key") or "").strip()
        model = (p.get("model") or "gpt-4o-mini").strip()
        if not base:
            raise ValueError("当前 OpenAI 兼容提供方缺少 base_url，请在设置中补全后再试。")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return "openai", model, {"base_url": base, "api_key": key}
    if kind == "azure":
        dep = (p.get("deployment") or "").strip() or s.azure_openai_deployment
        if not dep:
            raise ValueError("当前 Azure 提供方缺少 deployment，请在设置中补全后再试。")
        endpoint = (p.get("endpoint") or "").strip() or s.azure_openai_endpoint
        api_version = (p.get("api_version") or "").strip() or s.azure_openai_api_version
        api_key = (p.get("api_key") or "").strip() or s.azure_openai_api_key
        if not endpoint:
            raise ValueError("当前 Azure 提供方缺少 endpoint，请在设置中补全后再试。")
        if not api_version:
            raise ValueError("当前 Azure 提供方缺少 api_version，请在设置中补全后再试。")
        if not api_key:
            raise ValueError("当前 Azure 提供方缺少 api_key，请在设置中补全后再试。")
        return "azure", dep, {
            "endpoint": endpoint,
            "api_version": api_version,
            "api_key": api_key,
        }
    raise ValueError("模型提供方 kind 无效，仅支持 openai 或 azure。")


def get_llm_client(s, kind: str, openai_extra: dict):
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
    cache_key = f"{openai_extra.get('base_url','')}|{openai_extra.get('api_key','')[:12]}"
    if cache_key not in _openai_clients:
        _openai_clients[cache_key] = AsyncOpenAI(
            base_url=openai_extra["base_url"],
            api_key=openai_extra.get("api_key") or "EMPTY",
            timeout=LLM_HTTP_TIMEOUT,
        )
    return _openai_clients[cache_key]


def get_chat_client(llm_provider_id: str | None = None):
    """供笔记整理等单次调用：返回 (client, kind, model)。"""
    s = get_settings()
    kind, model, extra = resolve_llm(s, llm_provider_id)
    return get_llm_client(s, kind, extra), kind, model


def build_system_prompt(memories: list[dict]) -> str:
    skill_mgr = get_skill_manager()
    base = (
        "你是一个智能助手，能够帮助用户解答问题、分析信息、使用各种工具完成任务。\n"
        "回答时请使用 Markdown 格式，代码使用代码块，重要内容加粗。\n"
        "当你使用网页搜索结果时，请在回答中用 [数字] 标注引用来源，例如 [1]、[2]。\n"
    )
    if memories:
        mem_text = "\n".join(f"- {m['memory']}" for m in memories)
        base += f"\n关于用户的记忆信息（请在回答时参考）：\n{mem_text}\n"

    # 注入技能摘要（轻量，只有 name + description）
    skill_summary = skill_mgr.get_summary_prompt()
    if skill_summary:
        base += skill_summary

    return base


def _build_initial_tools(enable_search: bool, s) -> list[dict]:
    """构建初始工具列表（每次对话开始时）"""
    skill_mgr = get_skill_manager()
    mcp_mgr = get_mcp_manager()
    tools: list[dict] = []

    # 内置工具：网络搜索
    if enable_search and s.tavily_api_key:
        tools.append(search_service.TOOL_DEFINITION)

    # 内置工具：飞书发消息（写文档为独立 Skill feishu-write-doc）
    if s.feishu_app_id and s.feishu_app_secret:
        tools.append(feishu_service.TOOL_DEFINITION)

    # Skill tool.py 工具（直接注册，无需 get_skill_detail）
    tools.extend(skill_mgr.get_all_tool_definitions())

    # MCP 工具
    if mcp_mgr.available:
        tools.extend(mcp_mgr.tool_definitions)

    # get_skill_detail（当存在无 tool.py 的纯指令 Skill 时注册）
    pure_skills = [s for s in skill_mgr.enabled_skills if not s.tools]
    if pure_skills:
        tools.append(skill_mgr.get_skill_detail_definition)

    return tools or []


async def stream_chat(
    messages: list[dict],
    memories: list[dict],
    enable_search: bool = True,
    llm_provider_id: str | None = None,
) -> AsyncGenerator[dict, None]:
    """
    异步生成器，yield SSE 事件字典：
    - {"type": "token",          "content": "..."}
    - {"type": "searching",      "query": "..."}
    - {"type": "search_results", "results": [...]}
    - {"type": "tool_call",      "name": "...", "status": "..."}
    - {"type": "done",           "citations": [...]}
    - {"type": "error",          "message": "..."}
    """
    s = get_settings()
    kind, model_name, openai_extra = resolve_llm(s, llm_provider_id)
    client = get_llm_client(s, kind, openai_extra)
    system_prompt = build_system_prompt(memories)
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    # tools 在循环内可动态追加（get_skill_detail 触发后追加该 Skill 的工具）
    tools = _build_initial_tools(enable_search, s)
    all_citations: list[dict] = []
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    try:
        # 最多 6 轮工具调用（防止死循环）
        for _round in range(6):
            kwargs: dict = dict(
                model=model_name,
                messages=full_messages,
                stream=True,
                stream_options={"include_usage": True},
            )
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = await client.chat.completions.create(**kwargs)

            collected_content = ""
            collected_tool_calls: dict[int, dict] = {}
            finish_reason = None

            async for chunk in response:
                # 最后一个 chunk 没有 choices 但包含 usage
                if getattr(chunk, "usage", None):
                    u = chunk.usage
                    total_usage["prompt_tokens"] += u.prompt_tokens or 0
                    total_usage["completion_tokens"] += u.completion_tokens or 0
                    total_usage["total_tokens"] += u.total_tokens or 0
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                finish_reason = choice.finish_reason

                if choice.delta.content:
                    collected_content += choice.delta.content
                    yield {"type": "token", "content": choice.delta.content}

                if choice.delta.tool_calls:
                    for tc in choice.delta.tool_calls:
                        idx = tc.index
                        if idx not in collected_tool_calls:
                            collected_tool_calls[idx] = {
                                "id": tc.id or "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        if tc.id:
                            collected_tool_calls[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                collected_tool_calls[idx]["function"]["name"] += tc.function.name
                            if tc.function.arguments:
                                collected_tool_calls[idx]["function"]["arguments"] += tc.function.arguments

            if finish_reason != "tool_calls" or not collected_tool_calls:
                break

            # 把 assistant 的工具调用意图追加到消息历史
            full_messages.append({
                "role": "assistant",
                "content": collected_content or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                        },
                    }
                    for tc in collected_tool_calls.values()
                ],
            })

            # 并发执行所有工具调用
            tool_results = await _dispatch_tools(
                list(collected_tool_calls.values()),
                tools,
                all_citations,
            )

            for tc_id, tool_content, sse_events, new_tool_defs in tool_results:
                # 推送 SSE 事件
                for event in sse_events:
                    yield event
                # 追加工具结果到消息历史
                full_messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": tool_content,
                })
                # 动态追加新工具定义（get_skill_detail 返回的）
                for new_def in new_tool_defs:
                    if not any(t["function"]["name"] == new_def["function"]["name"] for t in tools):
                        tools.append(new_def)

        yield {"type": "done", "citations": all_citations, "usage": total_usage}

    except Exception as e:
        logger.exception("stream_chat 异常")
        yield {"type": "error", "message": str(e)}


async def _dispatch_tools(
    tool_calls: list[dict],
    current_tools: list[dict],
    all_citations: list[dict],
) -> list[tuple[str, str, list[dict], list[dict]]]:
    """
    并发执行所有工具调用。
    返回列表，每项为 (tool_call_id, tool_content, sse_events, new_tool_defs)
    """
    tasks = [
        _execute_tool(tc, current_tools, all_citations)
        for tc in tool_calls
    ]
    return await asyncio.gather(*tasks)


async def _execute_tool(
    tc: dict,
    current_tools: list[dict],
    all_citations: list[dict],
) -> tuple[str, str, list[dict], list[dict]]:
    """
    执行单个工具调用。
    返回 (tool_call_id, tool_content, sse_events, new_tool_defs)
    """
    tc_id = tc["id"]
    fn_name = tc["function"]["name"]
    sse_events: list[dict] = []
    new_tool_defs: list[dict] = []

    try:
        args = json.loads(tc["function"]["arguments"])
    except Exception:
        args = {}

    skill_mgr = get_skill_manager()
    mcp_mgr = get_mcp_manager()

    # ── 1. 内置：网络搜索 ──────────────────────────────────────
    if fn_name == "web_search":
        query = args.get("query", "")
        sse_events.append({"type": "searching", "query": query})

        results = await asyncio.get_event_loop().run_in_executor(
            None, search_service.search, query
        )
        offset = len(all_citations)
        for r in results:
            r["index"] = offset + r["index"]
        all_citations.extend(results)
        sse_events.append({"type": "search_results", "results": results})
        tool_content = _format_search_results(results)

    # ── 2. 内置：飞书发送 ──────────────────────────────────────
    elif fn_name == "feishu_send_message":
        content = args.get("content", "")
        sse_events.append({"type": "tool_call", "name": fn_name, "status": "sending"})
        result = await feishu_service.send_message(content)
        tool_content = "消息已成功发送到飞书。" if result["success"] else f"发送失败：{result.get('error', '未知错误')}"

    # ── 3. get_skill_detail（按需加载 Skill 详情 + 工具）──────
    elif fn_name == "get_skill_detail":
        skill_name = args.get("skill_name", "")
        skill = skill_mgr.get(skill_name)

        if skill and skill.enabled:
            tool_content = skill.detail
            # 把该 Skill 的工具追加到本轮 tools（动态注入）
            new_tool_defs = [t.definition for t in skill.tools.values()]
            sse_events.append({"type": "tool_call", "name": "get_skill_detail", "status": skill_name})
        else:
            tool_content = f"未找到技能 '{skill_name}'，可用技能：{[s.name for s in skill_mgr.enabled_skills]}"

    # ── 4. Skill tool.py 注册的工具 ───────────────────────────
    elif (skill_tool := skill_mgr.find_tool(fn_name)) is not None:
        skill = skill_mgr.get_skill_by_tool(fn_name)
        skill_name = skill.name if skill else fn_name
        sse_events.append({"type": "tool_call", "name": fn_name, "status": "running"})

        try:
            if asyncio.iscoroutinefunction(skill_tool.function):
                result = await skill_tool.function(**args)
            else:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: skill_tool.function(**args)
                )
            tool_content = str(result)
        except Exception as e:
            logger.error("Skill 工具执行失败 [%s]: %s", fn_name, e)
            tool_content = f"工具执行失败: {e}"

    # ── 5. MCP 工具 ───────────────────────────────────────────
    elif mcp_mgr.has_tool(fn_name):
        sse_events.append({"type": "tool_call", "name": fn_name, "status": "running"})
        tool_content = await mcp_mgr.call_tool(fn_name, args)

    # ── 未知工具 ──────────────────────────────────────────────
    else:
        logger.warning("未知工具调用: %s", fn_name)
        tool_content = f"未找到工具 '{fn_name}'"

    return tc_id, tool_content, sse_events, new_tool_defs


def _format_search_results(results: list[dict]) -> str:
    if not results:
        return "未找到相关搜索结果。"
    lines = ["以下是搜索结果，请基于这些内容回答，并在回答中用 [数字] 标注引用来源：\n"]
    for r in results:
        lines.append(f"[{r['index']}] 标题: {r['title']}")
        lines.append(f"    URL: {r['url']}")
        lines.append(f"    内容: {r['content']}\n")
    return "\n".join(lines)
