from fastapi import APIRouter, HTTPException, Query
from app.services import conversation as conv_service
from app.models.schemas import ConversationCreate

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("")
async def list_conversations():
    return await conv_service.list_conversations()


@router.post("")
async def create_conversation(body: ConversationCreate):
    return await conv_service.create_conversation(body.title)


@router.get("/search")
async def search_conversations(q: str = Query(..., min_length=1)):
    return await conv_service.search_conversations(q)


@router.get("/{conv_id}")
async def get_conversation(conv_id: str):
    conv = await conv_service.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.patch("/{conv_id}")
async def update_title(conv_id: str, body: ConversationCreate):
    conv = await conv_service.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await conv_service.update_conversation_title(conv_id, body.title or "新对话")
    return {"ok": True}


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: str):
    await conv_service.delete_conversation(conv_id)
    return {"ok": True}


@router.get("/{conv_id}/messages")
async def get_messages(conv_id: str):
    return await conv_service.get_messages(conv_id)
