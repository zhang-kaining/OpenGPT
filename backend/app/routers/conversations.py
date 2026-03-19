from fastapi import APIRouter, HTTPException, Query, Depends
from app.services import conversation as conv_service
from app.models.schemas import ConversationCreate
from app.deps import get_current_user

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(user: dict = Depends(get_current_user)):
    return await conv_service.list_conversations(user["id"])


@router.post("")
async def create_conversation(body: ConversationCreate, user: dict = Depends(get_current_user)):
    return await conv_service.create_conversation(user["id"], body.title)


@router.get("/search")
async def search_conversations(q: str = Query(..., min_length=1), user: dict = Depends(get_current_user)):
    return await conv_service.search_conversations(user["id"], q)


@router.get("/{conv_id}")
async def get_conversation(conv_id: str, user: dict = Depends(get_current_user)):
    conv = await conv_service.get_conversation(conv_id, user["id"])
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.patch("/{conv_id}")
async def update_title(conv_id: str, body: ConversationCreate, user: dict = Depends(get_current_user)):
    conv = await conv_service.get_conversation(conv_id, user["id"])
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await conv_service.update_conversation_title(conv_id, body.title or "新对话")
    return {"ok": True}


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: str, user: dict = Depends(get_current_user)):
    await conv_service.delete_conversation(conv_id, user["id"])
    return {"ok": True}


@router.get("/{conv_id}/messages")
async def get_messages(conv_id: str, user: dict = Depends(get_current_user)):
    conv = await conv_service.get_conversation(conv_id, user["id"])
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return await conv_service.get_messages(conv_id)
