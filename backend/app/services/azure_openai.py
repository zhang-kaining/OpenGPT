import json
import asyncio
from openai import AzureOpenAI
from app.config import get_settings
from app.services import web_search as search_service

settings = get_settings()

_client: AzureOpenAI | None = None
_SENTINEL = object()


def get_client() -> AzureOpenAI:
    global _client
    if _client is None:
        _client = AzureOpenAI(
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


def _sync_stream_to_queue(
    queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
    full_messages: list[dict],
    tools: list | None,
):
    """在线程池中运行同步流式调用，把事件放入队列"""
    client = get_client()
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

            response = client.chat.completions.create(**kwargs)

            collected_content = ""
            collected_tool_calls: dict[int, dict] = {}
            finish_reason = None

            for chunk in response:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                finish_reason = choice.finish_reason

                if choice.delta.content:
                    collected_content += choice.delta.content
                    asyncio.run_coroutine_threadsafe(
                        queue.put({"type": "token", "content": choice.delta.content}),
                        loop,
                    ).result()

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
                    if tc["function"]["name"] == "web_search":
                        try:
                            args = json.loads(tc["function"]["arguments"])
                            query = args.get("query", "")
                        except Exception:
                            query = ""

                        asyncio.run_coroutine_threadsafe(
                            queue.put({"type": "searching", "query": query}), loop
                        ).result()

                        results = search_service.search(query)
                        all_citations.extend(results)

                        asyncio.run_coroutine_threadsafe(
                            queue.put({"type": "search_results", "results": results}), loop
                        ).result()

                        tool_content = _format_search_results(results)
                        full_messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": tool_content,
                        })
                continue

            break

        asyncio.run_coroutine_threadsafe(
            queue.put({"type": "done", "citations": all_citations}), loop
        ).result()

    except Exception as e:
        asyncio.run_coroutine_threadsafe(
            queue.put({"type": "error", "message": str(e)}), loop
        ).result()
    finally:
        asyncio.run_coroutine_threadsafe(queue.put(_SENTINEL), loop).result()


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
    system_prompt = build_system_prompt(memories)
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    tools = [search_service.TOOL_DEFINITION] if enable_search and settings.tavily_api_key else None

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    # 在线程池中运行同步 Azure SDK 调用
    future = loop.run_in_executor(
        None,
        _sync_stream_to_queue,
        queue,
        loop,
        full_messages,
        tools,
    )

    while True:
        item = await queue.get()
        if item is _SENTINEL:
            break
        yield item

    # 确保线程任务完成，传播异常
    await future


def _format_search_results(results: list[dict]) -> str:
    if not results:
        return "未找到相关搜索结果。"
    lines = ["以下是搜索结果，请基于这些内容回答，并在回答中用 [数字] 标注引用来源：\n"]
    for r in results:
        lines.append(f"[{r['index']}] 标题: {r['title']}")
        lines.append(f"    URL: {r['url']}")
        lines.append(f"    内容: {r['content']}\n")
    return "\n".join(lines)
