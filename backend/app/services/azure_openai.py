import json
import asyncio
from openai import AsyncAzureOpenAI
from app.config import get_settings
from app.services import web_search as search_service
from app.services import feishu as feishu_service

settings = get_settings()

_client: AsyncAzureOpenAI | None = None


def get_client() -> AsyncAzureOpenAI:
    global _client
    if _client is None:
        _client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )
    return _client


def build_system_prompt(memories: list[dict]) -> str:
    base = (
        "你是一个智能助手，能够帮助用户解答问题、分析信息、进行网页搜索获取最新资讯。\n"
        "回答时请使用 Markdown 格式，代码使用代码块，重要内容加粗。\n"
        "当你使用网页搜索结果时，请在回答中用 [数字] 标注引用来源，例如 [1]、[2]。\n"
    )
    if memories:
        mem_text = "\n".join(f"- {m['memory']}" for m in memories)
        base += f"\n关于用户的记忆信息（请在回答时参考）：\n{mem_text}\n"
    return base


async def stream_chat(
    messages: list[dict],
    memories: list[dict],
    enable_search: bool = True,
):
    """
    异步生成器，yield SSE 事件字典：
    - {"type": "token", "content": "..."}
    - {"type": "searching", "query": "..."}
    - {"type": "search_results", "results": [...]}
    - {"type": "done", "citations": [...]}
    - {"type": "error", "message": "..."}
    """
    client = get_client()
    system_prompt = build_system_prompt(memories)
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    tools: list = []
    if enable_search and settings.tavily_api_key:
        tools.append(search_service.TOOL_DEFINITION)
    if settings.feishu_app_id and settings.feishu_app_secret:
        tools.append(feishu_service.TOOL_DEFINITION)
    tools = tools or None
    all_citations: list[dict] = []

    try:
        for _ in range(3):
            kwargs: dict = dict(
                model=settings.azure_openai_deployment,
                messages=full_messages,
                stream=True,
            )
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = await client.chat.completions.create(**kwargs)

            collected_content = ""
            collected_tool_calls: dict[int, dict] = {}
            finish_reason = None

            async for chunk in response:
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

            if finish_reason == "tool_calls" and collected_tool_calls:
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

                for tc in collected_tool_calls.values():
                    fn_name = tc["function"]["name"]

                    if fn_name == "web_search":
                        try:
                            args = json.loads(tc["function"]["arguments"])
                            query = args.get("query", "")
                        except Exception:
                            query = ""

                        yield {"type": "searching", "query": query}

                        results = await asyncio.get_event_loop().run_in_executor(
                            None, search_service.search, query
                        )
                        all_citations.extend(results)

                        yield {"type": "search_results", "results": results}

                        tool_content = _format_search_results(results)
                        full_messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": tool_content,
                        })

                    elif fn_name == "feishu_send_message":
                        try:
                            args = json.loads(tc["function"]["arguments"])
                            content = args.get("content", "")
                        except Exception:
                            content = ""

                        yield {"type": "tool_call", "name": "feishu_send_message", "status": "sending"}

                        result = await feishu_service.send_message(content)

                        if result["success"]:
                            tool_content = "消息已成功发送到飞书。"
                        else:
                            tool_content = f"发送失败：{result.get('error', '未知错误')}"

                        full_messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": tool_content,
                        })
                continue

            break

        yield {"type": "done", "citations": all_citations}

    except Exception as e:
        yield {"type": "error", "message": str(e)}


def _format_search_results(results: list[dict]) -> str:
    if not results:
        return "未找到相关搜索结果。"
    lines = ["以下是搜索结果，请基于这些内容回答，并在回答中用 [数字] 标注引用来源：\n"]
    for r in results:
        lines.append(f"[{r['index']}] 标题: {r['title']}")
        lines.append(f"    URL: {r['url']}")
        lines.append(f"    内容: {r['content']}\n")
    return "\n".join(lines)
