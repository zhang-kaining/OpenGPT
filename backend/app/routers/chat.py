import asyncio
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models.schemas import MessageCreate
from app.services import conversation as conv_service
from app.services import memory as mem_service
from app.services import azure_openai as oai_service
from app.config import get_settings

router = APIRouter(prefix="/api/chat", tags=["chat"])
settings = get_settings()


def sse(data: str) -> str:
    """格式化为标准 SSE 行"""
    return f"data: {data}\n\n"


@router.post("")
async def chat(body: MessageCreate):
    # 确保会话存在
    if body.conversation_id:
        conv = await conv_service.get_conversation(body.conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        conv_id = body.conversation_id
    else:
        conv = await conv_service.create_conversation()
        conv_id = conv["id"]

    # 保存用户消息（仅存文字部分）
    await conv_service.add_message(conv_id, "user", body.content)

    # 获取历史消息（最近 20 条，纯文字）
    history = await conv_service.get_messages(conv_id)
    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in history
        if m["role"] in ("user", "assistant")
    ][-20:]

    # 如果本次消息含图片，把最后一条 user 消息替换为 vision 格式
    if body.images:
        last_user = messages[-1] if messages and messages[-1]["role"] == "user" else None
        if last_user:
            content_parts: list[dict] = []
            if body.content.strip():
                content_parts.append({"type": "text", "text": body.content})
            for img_url in body.images:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": img_url, "detail": "auto"},
                })
            last_user["content"] = content_parts

    # 检索相关记忆
    memories = mem_service.search_memories(body.content, settings.user_id)

    async def event_generator():
        full_response = ""
        citations = []

        # 先推送会话 ID
        yield sse(json.dumps({"type": "conv_id", "conv_id": conv_id}, ensure_ascii=False))

        async for event in oai_service.stream_chat(messages, memories, body.enable_search):
            if event["type"] == "token":
                # 逐字拆分，产生打字机效果
                for char in event["content"]:
                    full_response += char
                    yield sse(json.dumps({"type": "token", "content": char}, ensure_ascii=False))
                    await asyncio.sleep(0.015)
            elif event["type"] in ("searching", "search_results"):
                yield sse(json.dumps(event, ensure_ascii=False))
            elif event["type"] == "done":
                citations = event.get("citations", [])
                yield sse(json.dumps(event, ensure_ascii=False))
            elif event["type"] == "error":
                yield sse(json.dumps(event, ensure_ascii=False))

        # 保存 AI 回复
        if full_response:
            await conv_service.add_message(conv_id, "assistant", full_response, citations or None)
            all_msgs = await conv_service.get_messages(conv_id)
            if len(all_msgs) == 2:
                title = body.content[:30].replace("\n", " ")
                await conv_service.update_conversation_title(conv_id, title)
            mem_service.add_memories(
                [{"role": "user", "content": body.content},
                 {"role": "assistant", "content": full_response}],
                settings.user_id
            )

        yield sse("[DONE]")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


