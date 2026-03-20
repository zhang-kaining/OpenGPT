import logging
from fastapi import APIRouter, Depends
from app.services import memory as mem_service
from app.deps import get_current_user

router = APIRouter(prefix="/api/memory", tags=["memory"])
logger = logging.getLogger(__name__)


@router.get("")
async def get_memories(user: dict = Depends(get_current_user)):
    user_id = user["id"]
    items = mem_service.get_all_memories(user_id)
    logger.info("memory_api get_all user_id=%s count=%d", user_id, len(items))
    return items


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str, user: dict = Depends(get_current_user)):
    mem_service.delete_memory(memory_id)
    return {"ok": True}
