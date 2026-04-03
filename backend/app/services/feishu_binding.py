import aiosqlite
import re
import secrets
import string
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.services import conversation as conv_service

_CODE_TTL_SECONDS = 120
_CODE_ALPHABET = string.ascii_uppercase + string.digits
_BIND_RE = re.compile(r"^/bind\s+([A-Za-z0-9]{4,32})\s*$", re.IGNORECASE)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fallback_user_id(open_id: str) -> str:
    return f"feishu:{(open_id or '').strip()}"


def _mask_open_id(open_id: str) -> str:
    raw = (open_id or "").strip()
    if len(raw) <= 8:
        return raw[:2] + "***" if raw else ""
    return raw[:4] + "***" + raw[-4:]


async def init_feishu_binding_tables() -> None:
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS feishu_bind_codes (
                code TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS feishu_user_bindings (
                open_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS feishu_sessions (
                open_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_feishu_bind_codes_user ON feishu_bind_codes(user_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_feishu_sessions_user ON feishu_sessions(user_id)"
        )
        await db.commit()


async def get_binding_status(user_id: str) -> dict:
    now = _now_iso()
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT open_id, created_at FROM feishu_user_bindings WHERE user_id = ?",
            (user_id,),
        ) as cur:
            bound_row = await cur.fetchone()
        async with db.execute(
            """
            SELECT code, expires_at
            FROM feishu_bind_codes
            WHERE user_id = ? AND used_at IS NULL AND expires_at > ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id, now),
        ) as cur:
            code_row = await cur.fetchone()
    return {
        "bound": bool(bound_row),
        "bound_open_id_masked": _mask_open_id(str(bound_row["open_id"])) if bound_row else "",
        "bound_at": str(bound_row["created_at"]) if bound_row else None,
        "active_code": str(code_row["code"]) if code_row else "",
        "active_code_expires_at": str(code_row["expires_at"]) if code_row else None,
    }


async def create_bind_code(user_id: str, ttl_seconds: int = _CODE_TTL_SECONDS) -> dict:
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    expires_at = (now_dt + timedelta(seconds=max(30, int(ttl_seconds)))).isoformat()
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT open_id FROM feishu_user_bindings WHERE user_id = ?",
            (user_id,),
        ) as cur:
            if await cur.fetchone():
                raise ValueError("当前网页账号已绑定飞书账号")
        await db.execute("DELETE FROM feishu_bind_codes WHERE user_id = ?", (user_id,))
        code = ""
        for _ in range(10):
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
            try:
                await db.execute(
                    """
                    INSERT INTO feishu_bind_codes(code, user_id, created_at, expires_at, used_at)
                    VALUES (?, ?, ?, ?, NULL)
                    """,
                    (code, user_id, now, expires_at),
                )
                await db.commit()
                return {"code": code, "expires_at": expires_at}
            except aiosqlite.IntegrityError:
                continue
    raise RuntimeError("生成绑定码失败，请稍后重试")


async def resolve_bound_user_id(open_id: str) -> str | None:
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        async with db.execute(
            "SELECT user_id FROM feishu_user_bindings WHERE open_id = ?",
            ((open_id or "").strip(),),
        ) as cur:
            row = await cur.fetchone()
    return str(row[0]) if row and row[0] else None


async def resolve_user_id(open_id: str) -> str:
    bound = await resolve_bound_user_id(open_id)
    return bound or _fallback_user_id(open_id)


def parse_bind_command(text: str) -> str | None:
    m = _BIND_RE.match((text or "").strip())
    if not m:
        return None
    return m.group(1).upper()


def is_new_command(text: str) -> bool:
    return (text or "").strip().lower() == "/new"


async def bind_open_id(open_id: str, code: str) -> dict:
    now = _now_iso()
    open_id = (open_id or "").strip()
    code = (code or "").strip().upper()
    if not open_id or not code:
        return {"ok": False, "message": "绑定码无效或已过期"}
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT code, user_id, expires_at, used_at FROM feishu_bind_codes WHERE code = ?",
            (code,),
        ) as cur:
            code_row = await cur.fetchone()
        if not code_row:
            return {"ok": False, "message": "绑定码无效或已过期"}
        if code_row["used_at"]:
            return {"ok": False, "message": "绑定码已使用，请重新生成"}
        if str(code_row["expires_at"]) <= now:
            return {"ok": False, "message": "绑定码已过期，请重新生成"}
        user_id = str(code_row["user_id"])
        async with db.execute(
            "SELECT user_id FROM feishu_user_bindings WHERE open_id = ?",
            (open_id,),
        ) as cur:
            row_by_open = await cur.fetchone()
        if row_by_open and str(row_by_open["user_id"]) != user_id:
            return {"ok": False, "message": "该飞书账号已绑定其他网页账号"}
        async with db.execute(
            "SELECT open_id FROM feishu_user_bindings WHERE user_id = ?",
            (user_id,),
        ) as cur:
            row_by_user = await cur.fetchone()
        if row_by_user and str(row_by_user["open_id"]) != open_id:
            return {"ok": False, "message": "当前网页账号已绑定其他飞书账号"}
        if row_by_open and str(row_by_open["user_id"]) == user_id:
            await db.execute(
                "UPDATE feishu_bind_codes SET used_at = ? WHERE code = ?",
                (now, code),
            )
            await db.commit()
            return {"ok": True, "message": "该飞书账号已完成绑定", "user_id": user_id}
        await db.execute(
            """
            INSERT INTO feishu_user_bindings(open_id, user_id, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(open_id) DO UPDATE SET
                user_id = excluded.user_id,
                created_at = excluded.created_at
            """,
            (open_id, user_id, now),
        )
        await db.execute(
            "UPDATE feishu_bind_codes SET used_at = ? WHERE code = ?",
            (now, code),
        )
        await db.commit()
    return {"ok": True, "message": "绑定成功，后续飞书消息将共享网页记忆", "user_id": user_id}


async def get_or_create_active_conversation(open_id: str, user_id: str) -> str:
    open_id = (open_id or "").strip()
    user_id = (user_id or "").strip() or _fallback_user_id(open_id)
    now = _now_iso()
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, conversation_id FROM feishu_sessions WHERE open_id = ?",
            (open_id,),
        ) as cur:
            row = await cur.fetchone()
        if row:
            conv_id = str(row["conversation_id"] or "")
            conv_user_id = str(row["user_id"] or "")
            conv = await conv_service.get_conversation(conv_id)
            if conv and conv_user_id == user_id and str(conv.get("user_id") or "") == user_id:
                await db.execute(
                    "UPDATE feishu_sessions SET updated_at = ? WHERE open_id = ?",
                    (now, open_id),
                )
                await db.commit()
                return conv_id
        conv = await conv_service.create_conversation(user_id, title="飞书对话")
        conv_id = str(conv["id"])
        await db.execute(
            """
            INSERT INTO feishu_sessions(open_id, user_id, conversation_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(open_id) DO UPDATE SET
                user_id = excluded.user_id,
                conversation_id = excluded.conversation_id,
                updated_at = excluded.updated_at
            """,
            (open_id, user_id, conv_id, now, now),
        )
        await db.commit()
        return conv_id


async def reset_active_conversation(open_id: str, user_id: str) -> str:
    open_id = (open_id or "").strip()
    user_id = (user_id or "").strip() or _fallback_user_id(open_id)
    now = _now_iso()
    conv = await conv_service.create_conversation(user_id, title="飞书对话")
    conv_id = str(conv["id"])
    async with aiosqlite.connect(get_settings().db_path, timeout=get_settings().sqlite_timeout_seconds) as db:
        await db.execute(
            """
            INSERT INTO feishu_sessions(open_id, user_id, conversation_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(open_id) DO UPDATE SET
                user_id = excluded.user_id,
                conversation_id = excluded.conversation_id,
                updated_at = excluded.updated_at
            """,
            (open_id, user_id, conv_id, now, now),
        )
        await db.commit()
    return conv_id
