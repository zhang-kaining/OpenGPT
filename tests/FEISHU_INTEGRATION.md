# 飞书长连接集成指南

## 概述

本项目已集成飞书长连接事件订阅功能，允许飞书消息触发本地对话。使用长连接模式，无需公网IP，适合桌面应用。

## 架构说明

### 长连接 vs Webhook

| 特性 | 长连接模式 | Webhook 模式 |
|------|-----------|-------------|
| 公网IP | 不需要 | 需要 |
| 部署复杂度 | 低 | 高 |
| 适用场景 | 桌面应用/本地开发 | 云服务/生产环境 |
| 连接方向 | 客户端主动连接飞书 | 飞书主动回调客户端 |

### 工作流程

1. 应用启动时，后端主动连接飞书服务器建立长连接
2. 飞书有新消息时，通过长连接推送事件到本地
3. 本地处理消息 -> 调用对话链路 -> 生成答案
4. 通过飞书API回发消息到飞书

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

依赖已包含 `lark-oapi>=1.2.0`（飞书官方Python SDK）

### 2. 配置飞书应用

#### 2.1 创建应用

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 获取 `APP_ID` 和 `APP_SECRET`

#### 2.2 配置事件订阅

1. 进入应用的「事件与回调」→「事件配置」
2. 订阅方式选择：**使用长连接接收事件**
3. 添加事件：`im.message.receive_v1`（接收消息事件）
4. 保存配置

#### 2.3 配置权限

确保应用有以下权限：
- `im:message`（发送消息）
- `im:message:group_at_msg`（群聊@消息，可选）
- `im:chat`（获取群聊信息，可选）

### 3. 配置本地环境

#### 方式一：通过 .env 文件

编辑 `backend/.env`：

```bash
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
FEISHU_DEFAULT_OPEN_ID=ou_xxxxxxxxxxxxxxxx  # 可选，默认接收者
```

#### 方式二：通过应用设置

启动应用后，在设置页面配置飞书应用信息。

### 4. 测试连接

```bash
# 测试飞书长连接
python3 test_feishu_connection.py
```

如果配置正确，会看到：
```
✅ 飞书事件客户端启动成功！
   运行状态: True
```

### 5. 启动应用

```bash
# 后台启动
bash start.sh start -d

# 或前台启动（调试用）
bash start.sh start
```

### 6. 验证功能

1. 在飞书中给应用发送消息
2. 检查后端日志：`tail -f logs/backend.log`
3. 应用应该能接收到消息并回复

## API 接口

### 查询飞书事件状态

```bash
curl http://localhost:18789/api/feishu/event-status
```

响应：
```json
{
  "running": true,
  "configured": true
}
```

### 查询飞书应用权限

```bash
curl http://localhost:18789/api/feishu/permissions
```

## 文件结构

```
backend/
├── app/
│   ├── services/
│   │   ├── feishu.py              # 飞书消息发送服务
│   │   └── feishu_event_client.py # 飞书长连接事件客户端（新增）
│   ├── config.py                  # 配置管理
│   └── main.py                    # 应用入口（已集成生命周期管理）
├── requirements.txt               # 依赖列表（已添加 lark-oapi）
test_feishu_connection.py          # 飞书连接测试脚本
```

## 安全建议

### 必须实现

1. **事件去重**：使用 `event_id` 防止重复处理
2. **回环保护**：忽略机器人自己发的消息
3. **输入验证**：限制消息长度，过滤空消息
4. **频控限流**：防止消息洪泛攻击

### 推荐实现

1. **签名校验**：验证事件来源（长连接模式已封装部分逻辑）
2. **白名单机制**：只允许特定用户/群聊触发
3. **审计日志**：记录所有事件处理（脱敏敏感信息）

## 故障排查

### 问题：客户端启动失败

**可能原因**：
- 未配置 `FEISHU_APP_ID` 或 `FEISHU_APP_SECRET`
- 网络无法访问飞书服务器
- 飞书应用未发布或未安装

**解决方法**：
1. 检查配置是否正确
2. 测试网络连接：`curl https://open.feishu.cn`
3. 在飞书开放平台发布应用并安装到测试租户

### 问题：收不到飞书消息

**可能原因**：
- 事件订阅未配置或未生效
- 应用权限不足
- 消息类型不支持

**解决方法**：
1. 检查飞书开放平台的事件配置
2. 确认应用已安装并启用
3. 查看后端日志确认事件是否到达

### 问题：长连接频繁断开

**可能原因**：
- Mac 系统休眠
- 网络切换
- 防火墙拦截

**解决方法**：
1. 添加自动重连逻辑（已实现基础版本）
2. 配置系统不休眠
3. 检查防火墙设置

## 下一步开发

当前版本已完成基础长连接建立，后续可以：

1. **实现消息处理逻辑**
   - 解析飞书消息事件
   - 调用对话链路生成回复
   - 回发消息到飞书

2. **完善用户/会话映射**
   - 飞书用户ID ↔ 本地用户ID
   - 飞书会话ID ↔ 本地会话ID

3. **增强安全控制**
   - 事件去重表
   - 频控限流
   - 白名单机制

4. **添加监控和日志**
   - 连接状态监控
   - 事件处理统计
   - 错误告警

## 参考资料

- [飞书开放平台文档](https://open.feishu.cn/document/)
- [飞书 Python SDK](https://github.com/larksuite/oapi-sdk-python)
- [长连接事件订阅](https://open.feishu.cn/document/server-docs/event-subscription-guide/event-subscription-mode/websocket-mode)
