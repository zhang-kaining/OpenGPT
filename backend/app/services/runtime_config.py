"""应用配置落库：固定路径 backend/data/settings.db（app_settings 表），与业务库 db_path 解耦。"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _BACKEND_ROOT / "data"
_SETTINGS_DB = Path(os.environ["SETTINGS_DB_PATH"]) if os.environ.get("SETTINGS_DB_PATH") else _DATA_DIR / "settings.db"


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY NOT NULL,
            value TEXT NOT NULL
        )
        """
    )


def _migrate_from_json_if_empty(conn: sqlite3.Connection) -> None:
    n = conn.execute("SELECT COUNT(*) FROM app_settings").fetchone()[0]
    if n > 0:
        return
    candidates = [
        _DATA_DIR / "runtime_config.json",
        Path((os.environ.get("DB_PATH") or "").strip() or "data/chat.db")
        .expanduser()
        .resolve()
        .parent
        / "runtime_config.json",
    ]
    seen: set[Path] = set()
    for p in candidates:
        try:
            rp = p.resolve()
        except OSError:
            rp = p
        if rp in seen or not p.is_file():
            continue
        seen.add(rp)
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not data:
                continue
            for k, v in data.items():
                conn.execute(
                    "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
                    (k, json.dumps(v, ensure_ascii=False)),
                )
            conn.commit()
            return
        except Exception:
            continue


def _row_to_dict(conn: sqlite3.Connection) -> dict[str, Any]:
    cur = conn.execute("SELECT key, value FROM app_settings")
    out: dict[str, Any] = {}
    for k, val in cur.fetchall():
        try:
            out[k] = json.loads(val)
        except json.JSONDecodeError:
            out[k] = val
    return out


def load_raw() -> dict[str, Any]:
    _SETTINGS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_SETTINGS_DB))
    try:
        _ensure_schema(conn)
        _migrate_from_json_if_empty(conn)
        return _row_to_dict(conn)
    finally:
        conn.close()


def save_raw(data: dict[str, Any]) -> None:
    _SETTINGS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_SETTINGS_DB))
    try:
        _ensure_schema(conn)
        conn.execute("DELETE FROM app_settings")
        for k, v in data.items():
            conn.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?)",
                (k, json.dumps(v, ensure_ascii=False)),
            )
        conn.commit()
    finally:
        conn.close()


def update_raw(partial: dict[str, Any]) -> dict[str, Any]:
    _SETTINGS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_SETTINGS_DB))
    try:
        _ensure_schema(conn)
        _migrate_from_json_if_empty(conn)
        for k, v in partial.items():
            if v is None or (isinstance(v, str) and not v.strip()):
                conn.execute("DELETE FROM app_settings WHERE key = ?", (k,))
            else:
                conn.execute(
                    "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
                    (k, json.dumps(v, ensure_ascii=False)),
                )
        conn.commit()
        return _row_to_dict(conn)
    finally:
        conn.close()


def mask_secrets(d: dict[str, Any], secret_suffixes: tuple[str, ...]) -> dict[str, Any]:
    out = dict(d)
    for k in list(out.keys()):
        if any(k.endswith(s) for s in secret_suffixes):
            v = out[k]
            if isinstance(v, str) and v.strip():
                out[k] = "***"
    return out
