import asyncio
import json
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from app.models.schemas import MessageCreate
from app.config import get_settings
from app.services import conversation as conv_service
from app.services import memory as mem_service
from app.services import azure_openai as oai_service
from app.deps import get_current_user

router = APIRouter(prefix="/api/chat", tags=["chat"])


def sse(data: str) -> str:
    """格式化为标准 SSE 行"""
    return f"data: {data}\n\n"


@router.post("")
async def chat(request: Request, body: MessageCreate, user: dict = Depends(get_current_user)):
    user_id = user["id"]
    try:
        # 先做提供方预检：未配置/配置非法时直接返回 400，而不是进入 SSE 流程后才报错
        oai_service.resolve_llm(get_settings(), body.llm_provider_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if body.conversation_id:
        conv = await conv_service.get_conversation(body.conversation_id, user_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        conv_id = body.conversation_id
    else:
        try:
            conv = await conv_service.create_conversation(user_id, folder_id=body.folder_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
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

    memories = mem_service.search_memories(body.content, user_id)

    async def event_generator():
        full_response = ""
        citations = []
        disconnected = False

        try:
            yield sse(json.dumps({"type": "conv_id", "conv_id": conv_id}, ensure_ascii=False))

            async for event in oai_service.stream_chat(
                messages, memories, body.enable_search, body.llm_provider_id
            ):
                if await request.is_disconnected():
                    disconnected = True
                    break

                if event["type"] == "token":
                    for char in event["content"]:
                        full_response += char
                        yield sse(json.dumps({"type": "token", "content": char}, ensure_ascii=False))
                        await asyncio.sleep(0.015)
                        if await request.is_disconnected():
                            disconnected = True
                            break
                    if disconnected:
                        break
                elif event["type"] in ("searching", "search_results"):
                    yield sse(json.dumps(event, ensure_ascii=False))
                elif event["type"] == "done":
                    citations = event.get("citations", [])
                    yield sse(json.dumps(event, ensure_ascii=False))
                elif event["type"] == "error":
                    yield sse(json.dumps(event, ensure_ascii=False))
        finally:
            if full_response:
                await conv_service.add_message(conv_id, "assistant", full_response, citations or None)
                all_msgs = await conv_service.get_messages(conv_id)
                if len(all_msgs) == 2:
                    title = body.content[:30].replace("\n", " ")
                    await conv_service.update_conversation_title(conv_id, title)
                if not disconnected:
                    mem_service.add_memories(
                        [{"role": "user", "content": body.content},
                         {"role": "assistant", "content": full_response}],
                        user_id
                    )

            if not disconnected:
                yield sse("[DONE]")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


