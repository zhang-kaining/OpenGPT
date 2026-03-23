import aiosqlite
import uuid
import json
from datetime import datetime, timezone
from typing import Optional
from app.config import get_settings


async def get_db():
    return await aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds)


async def init_db():
    import os
    os.makedirs(os.path.dirname(get_settings().db_path), exist_ok=True)
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversation_folders (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                parent_id TEXT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_conv_folders_user ON conversation_folders(user_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_conv_folders_parent ON conversation_folders(user_id, parent_id)"
        )
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                citations TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)
        # 兼容旧表：如果 user_id 列不存在则添加
        try:
            await db.execute("ALTER TABLE conversations ADD COLUMN user_id TEXT NOT NULL DEFAULT ''")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE conversations ADD COLUMN folder_id TEXT")
        except Exception:
            pass
        await db.commit()


async def create_conversation(
    user_id: str, title: Optional[str] = None, folder_id: Optional[str] = None
) -> dict:
    if folder_id:
        folder = await get_folder(folder_id, user_id)
        if not folder:
            raise ValueError("文件夹不存在或无权限")
    conv_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    title = title or "新对话"
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        await db.execute(
            "INSERT INTO conversations (id, user_id, title, created_at, updated_at, folder_id) VALUES (?, ?, ?, ?, ?, ?)",
            (conv_id, user_id, title, now, now, folder_id),
        )
        await db.commit()
    return {"id": conv_id, "title": title, "created_at": now, "updated_at": now, "folder_id": folder_id}


async def list_conversations(user_id: str) -> list:
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, title, created_at, updated_at, folder_id FROM conversations WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_conversation(conv_id: str, user_id: str = "") -> Optional[dict]:
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        db.row_factory = aiosqlite.Row
        if user_id:
            sql = "SELECT * FROM conversations WHERE id = ? AND user_id = ?"
            params = (conv_id, user_id)
        else:
            sql = "SELECT * FROM conversations WHERE id = ?"
            params = (conv_id,)
        async with db.execute(sql, params) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else None


async def update_conversation_title(conv_id: str, title: str):
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        await db.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, conv_id)
        )
        await db.commit()


async def delete_conversation(conv_id: str, user_id: str = ""):
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        if user_id:
            await db.execute("DELETE FROM conversations WHERE id = ? AND user_id = ?", (conv_id, user_id))
        else:
            await db.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        await db.commit()


async def add_message(
    conversation_id: str,
    role: str,
    content: str,
    citations: Optional[list] = None
) -> dict:
    msg_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    citations_json = json.dumps(citations) if citations else None
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        await db.execute(
            "INSERT INTO messages (id, conversation_id, role, content, citations, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, conversation_id, role, content, citations_json, now)
        )
        await db.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id)
        )
        await db.commit()
    return {
        "id": msg_id,
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "citations": citations,
        "created_at": now
    }


async def get_messages(conversation_id: str) -> list:
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,)
        ) as cursor:
            rows = await cursor.fetchall()
    result = []
    for r in rows:
        item = dict(r)
        item["citations"] = json.loads(item["citations"]) if item["citations"] else None
        result.append(item)
    return result


async def search_conversations(user_id: str, query: str) -> list:
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT DISTINCT c.id, c.title, c.created_at, c.updated_at, c.folder_id FROM conversations c "
            "LEFT JOIN messages m ON c.id = m.conversation_id "
            "WHERE c.user_id = ? AND (c.title LIKE ? OR m.content LIKE ?) "
            "ORDER BY c.updated_at DESC",
            (user_id, f"%{query}%", f"%{query}%"),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_folder(folder_id: str, user_id: str) -> Optional[dict]:
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM conversation_folders WHERE id = ? AND user_id = ?",
            (folder_id, user_id),
        ) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else None


async def list_folders(user_id: str) -> list:
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, parent_id, name, created_at, updated_at FROM conversation_folders WHERE user_id = ? ORDER BY name ASC",
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def create_folder(
    user_id: str, name: str, parent_id: Optional[str] = None
) -> dict:
    name = (name or "").strip() or "新建文件夹"
    if parent_id:
        p = await get_folder(parent_id, user_id)
        if not p:
            raise ValueError("父文件夹不存在或无权限")
    fid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        await db.execute(
            "INSERT INTO conversation_folders (id, user_id, parent_id, name, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (fid, user_id, parent_id, name, now, now),
        )
        await db.commit()
    return {"id": fid, "parent_id": parent_id, "name": name, "created_at": now, "updated_at": now}


async def _folder_subtree_ids(db: aiosqlite.Connection, user_id: str, folder_id: str) -> list[str]:
    db.row_factory = None
    async with db.execute(
        """
        WITH RECURSIVE sub(id) AS (
            SELECT id FROM conversation_folders WHERE id = ? AND user_id = ?
            UNION ALL
            SELECT f.id FROM conversation_folders f
            INNER JOIN sub ON f.parent_id = sub.id
            WHERE f.user_id = ?
        )
        SELECT id FROM sub
        """,
        (folder_id, user_id, user_id),
    ) as cur:
        rows = await cur.fetchall()
    return [r[0] for r in rows]


async def delete_folder(user_id: str, folder_id: str) -> bool:
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        ids = await _folder_subtree_ids(db, user_id, folder_id)
        if not ids:
            return False
        placeholders = ",".join("?" * len(ids))
        await db.execute(
            f"DELETE FROM conversations WHERE user_id = ? AND folder_id IN ({placeholders})",
            (user_id, *ids),
        )
        await db.execute(
            f"DELETE FROM conversation_folders WHERE user_id = ? AND id IN ({placeholders})",
            (user_id, *ids),
        )
        await db.commit()
    return True
