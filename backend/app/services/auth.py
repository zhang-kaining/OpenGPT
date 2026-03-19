import uuid
import jwt
import bcrypt
import aiosqlite
from datetime import datetime, timezone, timedelta
from app.config import get_settings

settings = get_settings()

SECRET_KEY = settings.azure_openai_api_key or "fallback-secret-key-change-me"
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30


async def init_users_table():
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_token(user_id: str, username: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


async def create_user(username: str, password: str, display_name: str = "") -> dict:
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    pw_hash = hash_password(password)
    display = display_name or username

    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "INSERT INTO users (id, username, password_hash, display_name, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, pw_hash, display, now),
        )
        await db.commit()

    return {"id": user_id, "username": username, "display_name": display}


async def get_user_by_username(username: str) -> dict | None:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE username = ?", (username,)) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def get_user_by_id(user_id: str) -> dict | None:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def change_password(user_id: str, old_password: str, new_password: str) -> bool:
    """修改密码，需验证旧密码。成功返回 True，旧密码错误返回 False。"""
    user = await get_user_by_id(user_id)
    if not user:
        return False
    if not verify_password(old_password, user["password_hash"]):
        return False

    pw_hash = hash_password(new_password)
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, user_id))
        await db.commit()
    return True


async def update_display_name(user_id: str, display_name: str):
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute("UPDATE users SET display_name = ? WHERE id = ?", (display_name, user_id))
        await db.commit()
