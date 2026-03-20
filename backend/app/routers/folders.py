from fastapi import APIRouter, HTTPException, Depends
from app.services import conversation as conv_service
from app.models.schemas import FolderCreate
from app.deps import get_current_user

router = APIRouter(prefix="/api/folders", tags=["folders"])


@router.get("")
async def list_folders(user: dict = Depends(get_current_user)):
    return await conv_service.list_folders(user["id"])


@router.post("")
async def create_folder(body: FolderCreate, user: dict = Depends(get_current_user)):
    if len(body.name.strip()) < 1:
        raise HTTPException(400, "文件夹名称不能为空")
    try:
        return await conv_service.create_folder(user["id"], body.name.strip(), body.parent_id)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.delete("/{folder_id}")
async def delete_folder(folder_id: str, user: dict = Depends(get_current_user)):
    ok = await conv_service.delete_folder(user["id"], folder_id)
    if not ok:
        raise HTTPException(404, detail="文件夹不存在")
    return {"ok": True}
