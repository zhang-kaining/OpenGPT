import httpx
from app.config import get_settings

settings = get_settings()

_token_cache: dict = {"token": "", "expires_at": 0}


async def get_tenant_access_token() -> str:
    """获取飞书 tenant_access_token，自动缓存"""
    import time
    if _token_cache["token"] and time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={
                "app_id": settings.feishu_app_id,
                "app_secret": settings.feishu_app_secret,
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"飞书获取 token 失败: {data}")

        import time
        _token_cache["token"] = data["tenant_access_token"]
        _token_cache["expires_at"] = time.time() + data.get("expire", 7200)
        return _token_cache["token"]


async def send_message(content: str, receive_id: str | None = None) -> dict:
    """
    发送飞书消息。
    receive_id: 接收者 open_id（ou_xxx）或 chat_id（oc_xxx）。
                不传则使用 .env 里的 FEISHU_DEFAULT_OPEN_ID。
    """
    target_id = receive_id or settings.feishu_default_open_id
    if not target_id:
        return {"success": False, "error": "未配置接收者 ID（FEISHU_DEFAULT_OPEN_ID）"}

    # 判断 ID 类型
    if target_id.startswith("oc_"):
        id_type = "chat_id"
    else:
        id_type = "open_id"

    token = await get_tenant_access_token()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://open.feishu.cn/open-apis/im/v1/messages",
            params={"receive_id_type": id_type},
            headers={"Authorization": f"Bearer {token}"},
            json={
                "receive_id": target_id,
                "msg_type": "text",
                "content": '{"text":"' + content.replace('"', '\\"').replace('\n', '\\n') + '"}',
            },
            timeout=15,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"success": False, "error": data.get("msg", "未知错误")}
        return {"success": True, "message_id": data.get("data", {}).get("message_id", "")}


# ---- Tool 定义（供 azure_openai.py 使用）----

TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "feishu_send_message",
        "description": (
            "将内容发送到飞书。当用户说发到飞书、发给我、推送到飞书时使用此工具。"
            "发送内容应为纯文本，可包含换行。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "要发送的消息内容，纯文本格式"
                }
            },
            "required": ["content"]
        }
    }
}
