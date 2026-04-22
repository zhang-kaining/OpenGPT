import mimetypes
import os
import shutil
import uuid
from datetime import datetime, timezone
from typing import Optional

import aiosqlite

from app.config import get_settings


async def init_note_tables() -> None:
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS note_folders (
                id         TEXT PRIMARY KEY,
                user_id    TEXT NOT NULL,
                parent_id  TEXT,
                name       TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_note_folders_user ON note_folders(user_id)"
        )
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id         TEXT PRIMARY KEY,
                user_id    TEXT NOT NULL,
                folder_id  TEXT,
                title      TEXT NOT NULL,
                content    TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_notes_user ON notes(user_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_notes_folder ON notes(user_id, folder_id)"
        )
        await db.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _note_image_base_dir() -> str:
    return os.path.join("data", "note-images")


def _safe_user_segment(user_id: str) -> str:
    return user_id.replace("\\", "_").replace("/", "_").replace("..", "_")


def _note_image_dir(user_id: str, note_id: str) -> str:
    return os.path.join(_note_image_base_dir(), _safe_user_segment(user_id), note_id)


def _guess_image_extension(content_type: str, filename: Optional[str] = None) -> str:
    if filename:
        suffix = os.path.splitext(filename)[1].lower()
        if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}:
            return suffix
    guessed = mimetypes.guess_extension(content_type or "") or ""
    if guessed == ".jpe":
        return ".jpg"
    return guessed if guessed else ".png"


def _remove_note_image_dir(user_id: str, note_id: str) -> None:
    image_dir = _note_image_dir(user_id, note_id)
    if os.path.isdir(image_dir):
        shutil.rmtree(image_dir, ignore_errors=True)


def _find_note_image_path(user_id: str, note_id: str, image_id: str) -> Optional[str]:
    image_dir = _note_image_dir(user_id, note_id)
    if not os.path.isdir(image_dir):
        return None
    prefix = f"{image_id}."
    for name in os.listdir(image_dir):
        if name.startswith(prefix):
            return os.path.join(image_dir, name)
    return None


# ── Folders ──────────────────────────────────────────────────────────────────

async def list_note_folders(user_id: str) -> list[dict]:
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, parent_id, name, created_at, updated_at "
            "FROM note_folders WHERE user_id = ? ORDER BY name ASC",
            (user_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def create_note_folder(user_id: str, name: str, parent_id: Optional[str] = None) -> dict:
    fid = str(uuid.uuid4())
    now = _now()
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        await db.execute(
            "INSERT INTO note_folders (id, user_id, parent_id, name, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (fid, user_id, parent_id, name.strip(), now, now),
        )
        await db.commit()
    return {"id": fid, "parent_id": parent_id, "name": name.strip(), "created_at": now, "updated_at": now}


async def _note_folder_subtree_ids(db: aiosqlite.Connection, user_id: str, folder_id: str) -> list[str]:
    db.row_factory = None
    async with db.execute(
        """
        WITH RECURSIVE sub(id) AS (
            SELECT id FROM note_folders WHERE id = ? AND user_id = ?
            UNION ALL
            SELECT f.id FROM note_folders f
            INNER JOIN sub ON f.parent_id = sub.id
            WHERE f.user_id = ?
        )
        SELECT id FROM sub
        """,
        (folder_id, user_id, user_id),
    ) as cur:
        rows = await cur.fetchall()
    return [r[0] for r in rows]


async def delete_note_folder(user_id: str, folder_id: str) -> bool:
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        ids = await _note_folder_subtree_ids(db, user_id, folder_id)
        if not ids:
            return False
        ph = ",".join("?" * len(ids))
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT id FROM notes WHERE user_id = ? AND folder_id IN ({ph})",
            (user_id, *ids),
        ) as cur:
            note_rows = await cur.fetchall()
        note_ids = [row["id"] for row in note_rows]
        ph = ",".join("?" * len(ids))
        await db.execute(
            f"DELETE FROM notes WHERE user_id = ? AND folder_id IN ({ph})",
            (user_id, *ids),
        )
        await db.execute(
            f"DELETE FROM note_folders WHERE user_id = ? AND id IN ({ph})",
            (user_id, *ids),
        )
        await db.commit()
    for note_id in note_ids:
        _remove_note_image_dir(user_id, note_id)
    return True


# ── Notes ─────────────────────────────────────────────────────────────────────

async def list_notes(user_id: str) -> list[dict]:
    """Return all notes (without content) for the sidebar list."""
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, folder_id, title, created_at, updated_at "
            "FROM notes WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def create_note(user_id: str, title: str, folder_id: Optional[str] = None, content: str = "") -> dict:
    nid = str(uuid.uuid4())
    now = _now()
    title = (title or "未命名").strip()
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        await db.execute(
            "INSERT INTO notes (id, user_id, folder_id, title, content, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (nid, user_id, folder_id, title, content, now, now),
        )
        await db.commit()
    return {"id": nid, "folder_id": folder_id, "title": title, "content": content,
            "created_at": now, "updated_at": now}


async def get_note(user_id: str, note_id: str) -> Optional[dict]:
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM notes WHERE id = ? AND user_id = ?",
            (note_id, user_id),
        ) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def save_note(user_id: str, note_id: str, title: Optional[str], content: Optional[str]) -> bool:
    note = await get_note(user_id, note_id)
    if not note:
        return False
    now = _now()
    new_title = (title or note["title"]).strip() or "未命名"
    new_content = content if content is not None else note["content"]
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        await db.execute(
            "UPDATE notes SET title = ?, content = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (new_title, new_content, now, note_id, user_id),
        )
        await db.commit()
    return True


async def delete_note(user_id: str, note_id: str) -> bool:
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        await db.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id))
        await db.commit()
    _remove_note_image_dir(user_id, note_id)
    return True


async def create_note_image(
    user_id: str,
    note_id: str,
    content: bytes,
    content_type: str,
    filename: Optional[str] = None,
) -> Optional[dict]:
    note = await get_note(user_id, note_id)
    if not note:
        return None
    ext = _guess_image_extension(content_type, filename)
    image_id = str(uuid.uuid4())
    image_dir = _note_image_dir(user_id, note_id)
    os.makedirs(image_dir, exist_ok=True)
    stored_name = f"{image_id}{ext}"
    path = os.path.join(image_dir, stored_name)
    with open(path, "wb") as f:
        f.write(content)
    return {
        "id": image_id,
        "filename": stored_name,
        "content_type": content_type,
        "size": len(content),
        "url": f"/api/notes/{note_id}/images/{image_id}",
    }


async def get_note_image(user_id: str, note_id: str, image_id: str) -> Optional[dict]:
    note = await get_note(user_id, note_id)
    if not note:
        return None
    path = _find_note_image_path(user_id, note_id, image_id)
    if not path:
        return None
    media_type, _ = mimetypes.guess_type(path)
    return {
        "path": path,
        "media_type": media_type or "application/octet-stream",
        "filename": os.path.basename(path),
    }
