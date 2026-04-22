import json

from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Query, Request
from fastapi.responses import StreamingResponse, FileResponse

from app.deps import get_current_user
from app.models.schemas import NoteCreate, NoteSave, NoteFolderCreate, AiRefineRequest
from app.services import note as note_service
from app.services.azure_openai import get_chat_client
from app.services import auth as auth_service

router = APIRouter(tags=["notes"])


def sse(data: str) -> str:
    return f"data: {data}\n\n"


# ── Note folders ──────────────────────────────────────────────────────────────

@router.get("/api/note-folders")
async def list_note_folders(user: dict = Depends(get_current_user)):
    return await note_service.list_note_folders(user["id"])


@router.post("/api/note-folders")
async def create_note_folder(body: NoteFolderCreate, user: dict = Depends(get_current_user)):
    if not body.name.strip():
        raise HTTPException(400, "文件夹名称不能为空")
    return await note_service.create_note_folder(user["id"], body.name, body.parent_id)


@router.delete("/api/note-folders/{folder_id}")
async def delete_note_folder(folder_id: str, user: dict = Depends(get_current_user)):
    ok = await note_service.delete_note_folder(user["id"], folder_id)
    if not ok:
        raise HTTPException(404, "文件夹不存在")
    return {"ok": True}


# ── Notes ─────────────────────────────────────────────────────────────────────

@router.get("/api/notes")
async def list_notes(user: dict = Depends(get_current_user)):
    return await note_service.list_notes(user["id"])


@router.post("/api/notes")
async def create_note(body: NoteCreate, user: dict = Depends(get_current_user)):
    return await note_service.create_note(
        user["id"], body.title, body.folder_id, body.content or ""
    )


@router.get("/api/notes/{note_id}")
async def get_note(note_id: str, user: dict = Depends(get_current_user)):
    note = await note_service.get_note(user["id"], note_id)
    if not note:
        raise HTTPException(404, "笔记不存在")
    return note


@router.patch("/api/notes/{note_id}")
async def save_note(note_id: str, body: NoteSave, user: dict = Depends(get_current_user)):
    ok = await note_service.save_note(user["id"], note_id, body.title, body.content)
    if not ok:
        raise HTTPException(404, "笔记不存在")
    return {"ok": True}


@router.delete("/api/notes/{note_id}")
async def delete_note(note_id: str, user: dict = Depends(get_current_user)):
    await note_service.delete_note(user["id"], note_id)
    return {"ok": True}


@router.post("/api/notes/{note_id}/images")
async def upload_note_image(
    note_id: str,
    image: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    content_type = (image.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(400, "仅支持图片文件")
    raw = await image.read()
    if not raw:
        raise HTTPException(400, "图片内容为空")
    saved = await note_service.create_note_image(
        user["id"],
        note_id,
        raw,
        content_type,
        image.filename,
    )
    if not saved:
        raise HTTPException(404, "笔记不存在")
    return saved


@router.get("/api/notes/{note_id}/images/{image_id}")
async def get_note_image(
    request: Request,
    note_id: str,
    image_id: str,
    token: str | None = Query(default=None),
):
    user = None
    header = request.headers.get("Authorization", "")
    header_token = header[7:] if header.startswith("Bearer ") else ""
    raw_token = header_token or token or ""
    if raw_token:
        payload = auth_service.decode_token(raw_token)
        if payload:
            auth_user = await auth_service.get_user_by_id(payload["sub"])
            if auth_user:
                user = {
                    "id": auth_user["id"],
                    "username": auth_user["username"],
                    "display_name": auth_user["display_name"],
                }
    if user is None:
        raise HTTPException(401, "未登录")
    image = await note_service.get_note_image(user["id"], note_id, image_id)
    if not image:
        raise HTTPException(404, "图片不存在")
    return FileResponse(
        image["path"],
        media_type=image["media_type"],
        filename=image["filename"],
    )


# ── AI refine（SSE） ──────────────────────────────────────────────────────────

@router.post("/api/notes/{note_id}/ai-refine")
async def ai_refine_note(
    note_id: str,
    body: AiRefineRequest,
    user: dict = Depends(get_current_user),
):
    note = await note_service.get_note(user["id"], note_id)
    if not note:
        raise HTTPException(404, "笔记不存在")

    instruction = (
        body.prompt
        or "请帮我整理以下内容，使结构清晰、逻辑分明，保留 Markdown 格式，分点列出关键信息，语言简洁。"
    )
    messages = [
        {"role": "system", "content": "你是一个专业的笔记整理助手，输出纯 Markdown，不要解释，直接给出整理后的内容。"},
        {"role": "user", "content": f"{instruction}\n\n---\n\n{note['content']}"},
    ]

    try:
        client, _kind, model = get_chat_client()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    async def event_generator():
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
            )
            async for chunk in response:
                if not getattr(chunk, "choices", None):
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield sse(json.dumps({"type": "token", "content": delta.content}, ensure_ascii=False))
            yield sse(json.dumps({"type": "done"}, ensure_ascii=False))
            yield sse("[DONE]")
        except Exception as e:
            yield sse(json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
