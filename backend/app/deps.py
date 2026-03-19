from fastapi import Depends, HTTPException, Request
from app.services import auth as auth_service


async def get_current_user(request: Request) -> dict:
    """从 Authorization header 解析当前用户，返回 user dict。"""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(401, "未登录")

    token = header[7:]
    payload = auth_service.decode_token(token)
    if not payload:
        raise HTTPException(401, "登录已过期，请重新登录")

    user = await auth_service.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(401, "用户不存在")

    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
    }
