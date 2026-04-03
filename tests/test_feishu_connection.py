#!/usr/bin/env python3
"""
测试飞书长连接事件客户端
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.feishu_event_client import get_feishu_event_client
from app.config import get_settings


async def test_feishu_connection():
    """测试飞书长连接"""
    print("=" * 60)
    print("飞书长连接测试")
    print("=" * 60)
    
    settings = get_settings()
    
    print(f"\n配置检查:")
    print(f"  APP_ID: {settings.feishu_app_id[:10]}..." if settings.feishu_app_id else "  APP_ID: 未配置")
    print(f"  APP_SECRET: {'已配置' if settings.feishu_app_secret else '未配置'}")
    
    if not settings.feishu_app_id or not settings.feishu_app_secret:
        print("\n❌ 错误: 未配置飞书 APP_ID 或 APP_SECRET")
        print("\n请配置飞书应用信息:")
        print("  1. 访问飞书开放平台: https://open.feishu.cn/")
        print("  2. 创建企业自建应用")
        print("  3. 获取 APP_ID 和 APP_SECRET")
        print("  4. 在应用设置中配置事件订阅（选择长连接模式）")
        print("  5. 在 .env 文件或应用设置中填入 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
        return False
    
    print("\n正在启动飞书事件客户端...")
    client = get_feishu_event_client()
    
    try:
        await client.start()
        
        if client.is_running():
            print("\n✅ 飞书事件客户端启动成功！")
            print(f"   运行状态: {client.is_running()}")
            
            print("\n保持运行 10 秒以验证连接稳定性...")
            await asyncio.sleep(10)
            
            print("\n✅ 连接稳定，测试通过")
            
            print("\n下一步:")
            print("  1. 在飞书开放平台配置事件订阅（长连接模式）")
            print("  2. 订阅事件: im.message.receive_v1")
            print("  3. 发布应用并在飞书中测试发送消息")
            print("  4. 启动完整应用: bash start.sh start -d")
            
            return True
        else:
            print("\n❌ 飞书事件客户端启动失败")
            return False
            
    except Exception as e:
        print(f"\n❌ 启动过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("\n正在停止客户端...")
        await client.stop()
        print("已停止")


if __name__ == "__main__":
    success = asyncio.run(test_feishu_connection())
    sys.exit(0 if success else 1)
