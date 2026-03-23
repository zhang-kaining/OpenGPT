from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.config import get_settings
from app.services import auth as auth_service
from app.deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterBody(BaseModel):
    username: str
    password: str
    display_name: str = ""


class LoginBody(BaseModel):
    username: str
    password: str


class ChangePasswordBody(BaseModel):
    old_password: str
    new_password: str


@router.post("/register")
async def register(body: RegisterBody):
    if len(body.username) < 2:
        raise HTTPException(400, "用户名至少 2 个字符")
    if len(body.password) < 6:
        raise HTTPException(400, "密码至少 6 个字符")

    existing = await auth_service.get_user_by_username(body.username)
    if existing:
        raise HTTPException(409, "用户名已存在")

    s = get_settings()
    if s.max_registered_users > 0:
        n = await auth_service.count_users()
        if n >= s.max_registered_users:
            raise HTTPException(
                403,
                f"注册人数已达上限（最多 {s.max_registered_users} 人），请联系管理员",
            )

    user = await auth_service.create_user(body.username, body.password, body.display_name)
    token = auth_service.create_token(user["id"], user["username"])
    return {"token": token, "user": user}


@router.post("/login")
async def login(body: LoginBody):
    user = await auth_service.get_user_by_username(body.username)
    if not user:
        raise HTTPException(401, "用户名或密码错误")
    if not auth_service.verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "用户名或密码错误")

    token = auth_service.create_token(user["id"], user["username"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
        },
    }


@router.post("/change-password")
async def change_password(body: ChangePasswordBody, user: dict = Depends(get_current_user)):
    if len(body.new_password) < 6:
        raise HTTPException(400, "新密码至少 6 个字符")
    ok = await auth_service.change_password(user["id"], body.old_password, body.new_password)
    if not ok:
        raise HTTPException(400, "旧密码不正确")
    return {"ok": True}


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    return user
