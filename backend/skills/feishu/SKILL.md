---
name: feishu
description: 将内容发送到飞书消息
enabled: true
requires_env: [FEISHU_APP_ID, FEISHU_APP_SECRET]
---

当用户说"发到飞书"、"发给我"、"推送到飞书"、"发飞书"时，调用 feishu_send_message 工具。

工具参数：
- content（必填）：要发送的消息内容，纯文本格式，支持换行

发送前无需二次确认，直接发送。发送成功后告知用户消息已送达。