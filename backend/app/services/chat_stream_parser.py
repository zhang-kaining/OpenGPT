from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChatRoundState:
    collected_content: str = ""
    collected_tool_calls: dict[int, dict] = field(default_factory=dict)
    finish_reason: str | None = None


def build_chat_request_kwargs(
    model_name: str,
    full_messages: list[dict],
    tools: list[dict],
) -> dict:
    kwargs: dict = {
        "model": model_name,
        "messages": full_messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    return kwargs


def consume_stream_chunk(
    chunk,
    state: ChatRoundState,
    total_usage: dict[str, int],
) -> list[dict]:
    events: list[dict] = []

    if getattr(chunk, "usage", None):
        usage = chunk.usage
        total_usage["prompt_tokens"] += usage.prompt_tokens or 0
        total_usage["completion_tokens"] += usage.completion_tokens or 0
        total_usage["total_tokens"] += usage.total_tokens or 0

    if not chunk.choices:
        return events

    choice = chunk.choices[0]
    state.finish_reason = choice.finish_reason

    if choice.delta.content:
        state.collected_content += choice.delta.content
        events.append({"type": "token", "content": choice.delta.content})

    if choice.delta.tool_calls:
        for tool_call in choice.delta.tool_calls:
            idx = tool_call.index
            if idx not in state.collected_tool_calls:
                state.collected_tool_calls[idx] = {
                    "id": tool_call.id or "",
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                }
            if tool_call.id:
                state.collected_tool_calls[idx]["id"] = tool_call.id
            if tool_call.function:
                if tool_call.function.name:
                    state.collected_tool_calls[idx]["function"]["name"] += tool_call.function.name
                if tool_call.function.arguments:
                    state.collected_tool_calls[idx]["function"]["arguments"] += tool_call.function.arguments

    return events


def should_continue_tool_loop(state: ChatRoundState) -> bool:
    return state.finish_reason == "tool_calls" and bool(state.collected_tool_calls)


def build_assistant_tool_call_message(state: ChatRoundState) -> dict:
    return {
        "role": "assistant",
        "content": state.collected_content or None,
        "tool_calls": [
            {
                "id": tool_call["id"],
                "type": "function",
                "function": {
                    "name": tool_call["function"]["name"],
                    "arguments": tool_call["function"]["arguments"],
                },
            }
            for tool_call in state.collected_tool_calls.values()
        ],
    }
