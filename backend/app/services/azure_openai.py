"""
流式对话编排入口。
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from app.services.chat_stream_parser import (
    ChatRoundState,
    build_assistant_tool_call_message,
    build_chat_request_kwargs,
    consume_stream_chunk,
    should_continue_tool_loop,
)
from app.services.llm_factory import get_chat_client
from app.services.prompt_builder import build_system_prompt
from app.services.tool_executor import dispatch_tool_calls
from app.services.tool_registry import build_initial_tools

logger = logging.getLogger(__name__)


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
    _ = enable_search  # 保持现有调用签名兼容，当前开关已不参与工具注入。

    client, _kind, model_name = get_chat_client(llm_provider_id)
    system_prompt = build_system_prompt(memories)
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    tools = build_initial_tools()
    all_citations: list[dict] = []
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    try:
        for _round in range(6):
            response = await client.chat.completions.create(
                **build_chat_request_kwargs(model_name, full_messages, tools)
            )
            round_state = ChatRoundState()

            async for chunk in response:
                for event in consume_stream_chunk(chunk, round_state, total_usage):
                    yield event

            if not should_continue_tool_loop(round_state):
                break

            full_messages.append(build_assistant_tool_call_message(round_state))

            tool_results = await dispatch_tool_calls(
                list(round_state.collected_tool_calls.values()),
                all_citations,
            )

            for result in tool_results:
                for event in result.sse_events:
                    yield event
                full_messages.append({
                    "role": "tool",
                    "tool_call_id": result.tool_call_id,
                    "content": result.content,
                })
                for new_def in result.new_tool_defs:
                    if not any(
                        existing["function"]["name"] == new_def["function"]["name"]
                        for existing in tools
                    ):
                        tools.append(new_def)

        yield {"type": "done", "citations": all_citations, "usage": total_usage}

    except Exception as exc:
        logger.exception("stream_chat 异常")
        yield {"type": "error", "message": str(exc)}
