from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import file_memory

router = APIRouter(prefix="/api/file-memory", tags=["file-memory"])

class LineCreate(BaseModel):
    text: str
    priority: str = "P3"
    kind: str = "fact"

class LineUpdate(BaseModel):
    text: str
    priority: str
    kind: str

class LinePin(BaseModel):
    priority: str = "P1"

@router.get("/files", summary="列出所有文件型记忆定义")
async def list_files() -> List[Dict[str, Any]]:
    return file_memory.list_memory_files()

@router.get("/{name}", summary="读取指定文件型记忆的所有行")
async def get_file_lines(name: str) -> List[Dict[str, Any]]:
    try:
        return file_memory.read_memory_file(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{name}/lines", summary="追加一行记忆")
async def add_line(name: str, req: LineCreate) -> Dict[str, str]:
    try:
        line_id = file_memory.append_memory_line(name, req.text, req.priority, req.kind)
        return {"id": line_id, "status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch("/{name}/lines/{line_id}", summary="更新一行记忆")
async def update_line(name: str, line_id: str, req: LineUpdate) -> Dict[str, str]:
    try:
        success = file_memory.update_memory_line(name, line_id, req.text, req.priority, req.kind)
        if not success:
            raise HTTPException(status_code=404, detail="Line not found")
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/{name}/lines/{line_id}", summary="删除一行记忆")
async def delete_line(name: str, line_id: str) -> Dict[str, str]:
    try:
        success = file_memory.delete_memory_line(name, line_id)
        if not success:
            raise HTTPException(status_code=404, detail="Line not found")
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{name}/lines/{line_id}/pin", summary="提升一行记忆的优先级")
async def pin_line(name: str, line_id: str, req: LinePin) -> Dict[str, str]:
    try:
        success = file_memory.promote_memory_line(name, line_id, req.priority)
        if not success:
            raise HTTPException(status_code=404, detail="Line not found")
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
