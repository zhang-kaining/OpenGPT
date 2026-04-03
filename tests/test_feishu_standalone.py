#!/usr/bin/env python3
"""
独立测试飞书长连接（不依赖 FastAPI）
"""
import sys
import os
import time
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_feishu_long_connection():
    """测试飞书长连接"""
    print("=" * 80)
    print("飞书长连接独立测试")
    print("=" * 80)
    
    settings = get_settings()
    
    print(f"\n配置检查:")
    print(f"  APP_ID: {settings.feishu_app_id[:10]}..." if settings.feishu_app_id else "  APP_ID: 未配置 ❌")
    print(f"  APP_SECRET: {'已配置 ✅' if settings.feishu_app_secret else '未配置 ❌'}")
    
    if not settings.feishu_app_id or not settings.feishu_app_secret:
        print("\n❌ 错误: 未配置飞书 APP_ID 或 APP_SECRET")
        print("\n请先配置飞书应用信息，然后再运行此测试")
        return False
    
    try:
        import lark_oapi as lark
        
        print("\n正在初始化飞书长连接客户端...")
        
        def handle_message_received(data):
            print("\n" + "=" * 80)
            print("🎉🎉🎉 收到飞书消息事件！🎉🎉🎉")
            print("=" * 80)
            print(f"原始数据:\n{lark.JSON.marshal(data, indent=2)}")
            
            try:
                if hasattr(data, 'event'):
                    event = data.event
                    message = event.message if hasattr(event, 'message') else None
                    
                    if message:
                        content = message.content if hasattr(message, 'content') else ""
                        message_id = message.message_id if hasattr(message, 'message_id') else ""
                        chat_id = message.chat_id if hasattr(message, 'chat_id') else ""
                        sender = event.sender if hasattr(event, 'sender') else None
                        sender_id = sender.sender_id if sender and hasattr(sender, 'sender_id') else ""
                        
                        print(f"\n📨 消息ID: {message_id}")
                        print(f"💬 会话ID: {chat_id}")
                        print(f"👤 发送者ID: {sender_id}")
                        print(f"📝 消息内容: {content}")
                        print("\n✅ 消息接收成功！")
            except Exception as e:
                print(f"\n❌ 解析消息失败: {e}")
                import traceback
                traceback.print_exc()
        
        event_handler = lark.EventDispatcherHandler.builder("", "") \
            .register_p2_im_message_receive_v1(handle_message_received) \
            .build()
        
        ws_client = lark.ws.Client(
            settings.feishu_app_id,
            settings.feishu_app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.DEBUG
        )
        
        print("\n✅ 客户端初始化成功")
        print("\n正在建立长连接...")
        print("提示: 连接成功后会显示 'connected to wss://...'")
        print("\n" + "=" * 80)
        print("监听中... 请在飞书中给你的机器人发送消息")
        print("按 Ctrl+C 停止")
        print("=" * 80 + "\n")
        
        ws_client.start()
        
    except KeyboardInterrupt:
        print("\n\n用户中断，正在停止...")
        return True
    except ImportError as e:
        print(f"\n❌ 飞书 SDK 未安装: {e}")
        print("请运行: pip install lark-oapi python-socks")
        return False
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = test_feishu_long_connection()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n测试已停止")
        sys.exit(0)
