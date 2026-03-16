import aiosqlite
import uuid
import json
from datetime import datetime, timezone
from typing import Optional
from app.config import get_settings

settings = get_settings()


async def get_db():
    return await aiosqlite.connect(settings.db_path)


async def init_db():
    import os
    os.makedirs(os.path.dirname(settings.db_path), exist_ok=True)
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
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
        await db.commit()


async def create_conversation(title: Optional[str] = None) -> dict:
    conv_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    title = title or "新对话"
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (conv_id, title, now, now)
        )
        await db.commit()
    return {"id": conv_id, "title": title, "created_at": now, "updated_at": now}


async def list_conversations() -> list:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM conversations ORDER BY updated_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_conversation(conv_id: str) -> Optional[dict]:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM conversations WHERE id = ?", (conv_id,)
        ) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else None


async def update_conversation_title(conv_id: str, title: str):
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, conv_id)
        )
        await db.commit()


async def delete_conversation(conv_id: str):
    async with aiosqlite.connect(settings.db_path) as db:
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
    async with aiosqlite.connect(settings.db_path) as db:
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
    async with aiosqlite.connect(settings.db_path) as db:
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


async def search_conversations(query: str) -> list:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT DISTINCT c.* FROM conversations c "
            "LEFT JOIN messages m ON c.id = m.conversation_id "
            "WHERE c.title LIKE ? OR m.content LIKE ? "
            "ORDER BY c.updated_at DESC",
            (f"%{query}%", f"%{query}%")
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]
