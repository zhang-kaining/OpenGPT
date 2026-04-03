#!/usr/bin/env python3
"""
飞书长连接最小官方示例（仅验证事件是否到达）
"""
import os
import sys

import lark_oapi as lark


def main() -> int:
    app_id = (os.getenv("FEISHU_APP_ID") or "").strip()
    app_secret = (os.getenv("FEISHU_APP_SECRET") or "").strip()

    if not app_id or not app_secret:
        print("❌ 缺少环境变量 FEISHU_APP_ID / FEISHU_APP_SECRET")
        print("示例：")
        print("  export FEISHU_APP_ID=cli_xxx")
        print("  export FEISHU_APP_SECRET=xxx")
        return 1

    print("=" * 72)
    print("飞书长连接最小示例")
    print("=" * 72)
    print(f"APP_ID: {app_id[:10]}...")
    print("正在建立连接，等待事件...")
    print("请在飞书中给机器人发消息（群里需 @机器人）")
    print("按 Ctrl+C 退出")

    def on_im_message(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
        print("\n" + "=" * 72)
        print("✅ 收到 im.message.receive_v1")
        print("=" * 72)
        print(lark.JSON.marshal(data, indent=2))

    event_handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(on_im_message)
        .build()
    )

    ws_client = lark.ws.Client(
        app_id,
        app_secret,
        event_handler=event_handler,
        log_level=lark.LogLevel.DEBUG,
    )

    ws_client.start()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已停止")
        sys.exit(0)


# export FEISHU_APP_ID=cli_a9341bd6af78dcc1
# export FEISHU_APP_SECRET=ygM6wsJ2bl6vjBkYkUj0KekT3XFpq0h3