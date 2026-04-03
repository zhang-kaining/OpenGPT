#!/usr/bin/env python3
"""
测试飞书 API 调用（不依赖长连接）
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.config import get_settings
import httpx
import asyncio


async def test_feishu_api():
    """测试飞书 API 调用"""
    print("=" * 80)
    print("飞书 API 测试")
    print("=" * 80)
    
    settings = get_settings()
    
    print(f"\n配置检查:")
    print(f"  APP_ID: {settings.feishu_app_id[:10]}..." if settings.feishu_app_id else "  APP_ID: 未配置 ❌")
    print(f"  APP_SECRET: {'已配置 ✅' if settings.feishu_app_secret else '未配置 ❌'}")
    
    if not settings.feishu_app_id or not settings.feishu_app_secret:
        print("\n❌ 错误: 未配置飞书 APP_ID 或 APP_SECRET")
        return False
    
    try:
        # 1. 获取 tenant_access_token
        print("\n【步骤1】获取 tenant_access_token...")
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
                print(f"❌ 获取 token 失败: {data}")
                return False
            
            token = data["tenant_access_token"]
            print(f"✅ Token 获取成功: {token[:20]}...")
        
        # 2. 获取应用信息
        print("\n【步骤2】获取应用信息...")
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://open.feishu.cn/open-apis/app/v3/apps/" + settings.feishu_app_id,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            data = resp.json()
            print(f"应用信息: {data}")
        
        # 3. 获取机器人信息
        print("\n【步骤3】获取机器人信息...")
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://open.feishu.cn/open-apis/bot/v3/info",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            data = resp.json()
            print(f"机器人信息: {data}")
        
        print("\n" + "=" * 80)
        print("✅ API 调用测试完成")
        print("=" * 80)
        print("\n提示:")
        print("1. 如果 API 调用成功，说明应用配置正确")
        print("2. 长连接收不到消息，可能是事件订阅配置问题")
        print("3. 请检查飞书开放平台的「事件与回调」配置")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_feishu_api())
    sys.exit(0 if success else 1)
