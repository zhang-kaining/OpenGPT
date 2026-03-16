from fastapi import APIRouter, HTTPException
from app.services import memory as mem_service
from app.config import get_settings

router = APIRouter(prefix="/api/memory", tags=["memory"])
settings = get_settings()


@router.get("")
async def get_memories():
    return mem_service.get_all_memories(settings.user_id)


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str):
    mem_service.delete_memory(memory_id)
    return {"ok": True}
