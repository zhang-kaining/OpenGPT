from fastapi import APIRouter, Depends
from app.services import memory as mem_service
from app.deps import get_current_user

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("")
async def get_memories(user: dict = Depends(get_current_user)):
    return mem_service.get_all_memories(user["id"])


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str, user: dict = Depends(get_current_user)):
    mem_service.delete_memory(memory_id)
    return {"ok": True}
