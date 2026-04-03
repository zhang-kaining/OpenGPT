# 飞书触发对话支持
_Exported on 2026/3/30 at GMT+8 22:00:05 from Cursor (2.6.22)_

---

**User**

帮我看看如果想支持飞书触发对话，需要怎么改动

---

**Cursor**

我先快速梳理当前项目里“对话触发”的入口和后端接口，再结合飞书常见接入方式给你一份最小改动方案（前后端各改哪里、数据流怎么走）。先查路由与消息发送链路。

我已经看到后端有现成的飞书能力（发消息、写文档），下一步会确认“对话入口”当前是否只支持前端 SSE，以及鉴权是否允许飞书 webhook 直接调用。

你这个项目已经有“**从模型发消息到飞书**”能力了，但还没有“**飞书消息触发本地对话**”入口。  
核心结论：要加一个**飞书事件回调 Webhook 路由**，把飞书消息转换成现有聊天链路，再把结果回发飞书。

现状证据（代码里）：

```20:24:backend/app/routers/chat.py
@router.post("")
async def chat(request: Request, body: MessageCreate, user: dict = Depends(get_current_user)):
    user_id = user["id"]
```

`/api/chat` 强依赖登录态（Bearer token），飞书回调不能直接调用它。

```156:189:backend/app/services/feishu.py
async def send_message(content: str, receive_id: str | None = None) -> dict:
    ...
    resp = await client.post(
        "https://open.feishu.cn/open-apis/im/v1/messages",
```

这里只有“主动发消息”，没有“接收飞书事件并回复”链路。

---

## 你需要改的地方（最小可行）

- 新增路由：`backend/app/routers/feishu_webhook.py`
  - `POST /api/feishu/webhook`
  - 处理两类事件：
    - URL 校验（返回 `challenge`）
    - `im.message.receive_v1`（收到文本消息）
- 新增“非流式对话编排”函数（建议抽到 `conversation_orchestrator`）
  - 复用你现在 `chat.py` 的核心流程：建/取会话、落库、拼 history、调用 `azure_openai.stream_chat` 聚合全文、写 assistant 消息、写 memory。
  - 但返回 `str`（完整答案），不走 SSE。
- 新增飞书回复函数（service）
  - 推荐按 `message_id` 回复，避免找人 ID。
  - 例如 `reply_message(message_id, content)`。
- `backend/app/main.py` 注册新 router。
- 配置项新增（建议）：
  - `FEISHU_EVENT_VERIFICATION_TOKEN`（或签名校验相关）
  - 如你开启加密事件，再加 `FEISHU_ENCRYPT_KEY`。

---

## 关键设计建议（避免踩坑）

- **身份映射**：飞书用户 `open_id` -> 本系统 `user_id`
  - 最简：先统一写入一个固定账号（如 `feishu_bot_user`）。
  - 更好：建 `feishu_user_bindings` 表，做多用户隔离。
- **会话映射**：飞书 `chat_id + open_id` -> `conversation_id`
  - 不做映射会导致每条消息都新对话。
- **去重**：按 `event_id` 防重放（飞书会重试）。
- **回环保护**：忽略 bot 自己发的消息，避免自问自答。
- **工具约束**：飞书入口下建议禁用 `feishu_send_message` 工具，防止模型再触发“发飞书”形成双发/循环。

---

## 前端要不要改？

- **不需要**。这是后端新增 webhook 能力，前端聊天 UI 可以不动。
- 除非你还想在设置页加“飞书回调配置状态”，那才需要前端改。

---

## 推荐实施顺序（省事版）

1. 先做 webhook 路由 + URL 校验。
2. 收到消息后先写死回一条“已收到”（验证链路）。
3. 接入现有 LLM 流程，聚合文本后回飞书。
4. 再补用户/会话映射与去重表。
5. 最后补签名校验与监控日志。

---

如果你愿意，我可以下一步直接给你一版**按你当前代码结构贴合的伪代码/接口草图**（包含 `feishu_webhook.py` 的函数签名、事件 JSON 解析字段、以及如何复用 `chat.py` 逻辑）。

---

**User**

怎么保证安全，不会被攻击，我的后端服务怎么接收到飞书的信息的，是飞书发送https请求吗

---

**Cursor**

是的，你理解对了：**飞书会主动向你的后端回调地址发 HTTPS POST 请求**（事件订阅/Webhook）。

结合你当前项目，建议这样理解：

```20:23:backend/app/routers/chat.py
@router.post("")
async def chat(request: Request, body: MessageCreate, user: dict = Depends(get_current_user)):
    user_id = user["id"]
```

你现在的聊天入口是给前端登录用户用的（Bearer 鉴权），**不是**给飞书直接调用的。所以要新增一个专门的飞书 webhook 路由。

---

## 1) 后端如何接收到飞书信息

- 在飞书开发者后台配置事件订阅 URL，例如：`https://你的域名/api/feishu/webhook`
- 飞书服务器有新消息时，向这个 URL 发 HTTPS 请求（JSON）
- 你的服务解析事件后，再调用你已有的对话能力处理
- 最后调用飞书开放接口把回复发回去（你项目里这部分已有）

你项目里“发回飞书”已存在：

```172:178:backend/app/services/feishu.py
token = await get_tenant_access_token()

async with httpx.AsyncClient() as client:
    resp = await client.post(
        "https://open.feishu.cn/open-apis/im/v1/messages",
```

---

## 2) 怎么保证安全（重点）

至少做这 8 层：

- **签名校验**：校验飞书请求头里的签名/时间戳/nonce（防伪造）
- **challenge 校验**：仅按飞书协议返回 challenge，不做多余逻辑
- **时间窗校验**：`timestamp` 超过几分钟直接拒绝（防重放）
- **事件去重**：按 `event_id` 落库去重（飞书重试时不重复处理）
- **最小暴露面**：Webhook 路由不复用你现有 `/api/chat`，独立实现
- **权限最小化**：飞书应用只开必须权限，不开多余 scope
- **密钥保护**：`app_secret / encrypt_key / verification_token` 只放服务端配置
- **限流与防刷**：Nginx/API 网关加 rate limit，异常高频自动拦截

---

## 3) 常见攻击面与对应防护

- **伪造请求**：靠签名校验拦截
- **重放攻击**：时间窗 + `event_id` 去重
- **刷接口 DoS**：网关限流 + 超时 + 异步队列
- **消息注入滥用模型**：长度限制、敏感词/指令白名单、工具调用约束
- **回环（机器人回复自己）**：过滤 bot 自己发出的消息

---

## 4) 部署侧必须满足

- 回调 URL 必须公网可达，且 HTTPS 证书有效
- 本地开发可用隧道（如 Cloudflare Tunnel/ngrok）临时暴露
- 生产建议：`Nginx -> FastAPI`，并在 Nginx 层做 TLS、限流、日志审计

---

如果你要，我下一条可以给你一份“**飞书 webhook 安全校验清单 + Python 伪代码模板**”，按你这个项目结构直接套。

---

**User**

有个问题，我是桌面版本，我的mac是不是不能公网可达，调用ngrok也不太好

---

**Cursor**

对，你这个判断很准确：**桌面版跑在你本机 Mac 上，默认不是公网可达**，飞书就没法直接回调到你本地 `https://.../webhook`。

你有 3 个可行方案（按推荐顺序）：

- **方案A（最推荐）: 飞书“长连接接收事件”模式**  
  不需要公网回调地址。你的本地客户端主动连飞书服务器，飞书把事件通过这条连接推过来。  
  适合你这种“本机桌面应用、又不想用 ngrok”。

- **方案B: 极小云中转（只做转发）**  
  云上放一个很薄的 webhook 服务（验签+转发），再把消息发到你本机（你主动轮询或保持反向通道）。  
  成本低，但架构比 A 稍复杂。

- **方案C: 临时隧道（ngrok/cloudflared）**  
  开发调试方便，但你已经说不太好，生产也不稳定，不建议长期依赖。

---

### 你这个项目最现实的落地建议

- 继续保留你现在本地对话引擎（`chat.py` 这套）。
- 新增一个“飞书事件接入层”，优先用**长连接模式**拿消息。
- 收到事件后走你现有对话服务，再调用你已有的 `feishu.send_message` 回发。

---

### 安全上怎么做（长连接也同样要做）

- 校验事件签名/解密（按飞书配置）
- `event_id` 去重
- 过滤机器人自己消息
- 严格限制触发范围（只响应指定 chat/user）
- 做频控和异常熔断

---

如果你愿意，我可以下一步给你一份“**桌面版 + 飞书长连接模式**”的最小改造清单（具体到你这个仓库该新增哪些文件、哪些函数）。

---

**User**

详细说说方案A怎么执行

---

**Cursor**

我先补一眼你后端当前依赖里有没有飞书长连接 SDK，再按你仓库结构给一份“可直接照着做”的执行步骤和代码骨架。

可以，下面给你一版**桌面版可落地**的方案A执行手册。  
方案A就是：**飞书长连接事件订阅（不需要公网 webhook）**。

---

## 方案A整体链路

1. 你的桌面应用启动后，后端进程主动连飞书事件通道（WebSocket/长连接）。
2. 飞书有新消息时，通过这条连接推事件到你本机。
3. 你本机处理消息 -> 调用现有对话链路 -> 生成答案。
4. 再用你已有 `send_message` 接口回发飞书。

你现在项目里“回发飞书”已经有了（`backend/app/services/feishu.py`），缺的是“接收飞书事件”这一段。

---

## 你仓库当前适配点（已确认）

- 启动生命周期入口在 `backend/app/main.py` 的 `lifespan`，适合挂长连接客户端启动/停止。
- 对话主流程现在写在 `backend/app/routers/chat.py`，是 SSE + 登录态接口，不适合直接被飞书事件复用。
- 依赖里还没有飞书长连接 SDK（`backend/requirements.txt` 里没有）。

---

## 具体执行步骤

### 1) 飞书后台改为“长连接订阅”
在飞书开发者后台：

- 事件订阅方式选“长连接”
- 订阅事件至少加：接收消息事件（通常是 `im.message.receive_v1`）
- 开通消息读取/发送相关权限（具体权限名按后台提示）
- 发布版本并在测试租户安装应用

> 这一步后，不需要公网回调 URL。

---

### 2) 后端新增“飞书事件客户端”服务

建议新建：`backend/app/services/feishu_event_client.py`

职责：

- `start()`：建立长连接，注册事件处理器
- `stop()`：优雅关闭
- `on_message_event(event)`：收到飞书消息后的业务逻辑

---

### 3) 在 FastAPI 生命周期里启动它

你现在有：

```21:30:backend/app/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_users_table()
    await init_note_tables()
    get_skill_manager().load()
    await get_mcp_manager().load()
    yield
```

改造思路（不改代码，仅说明）：

- `yield` 前 `await feishu_event_client.start()`
- `yield` 后 `await feishu_event_client.stop()`

这样桌面版启动后自动连飞书，退出时断开。

---

### 4) 把“对话编排”从 `chat.py` 抽成可复用函数

因为当前 `/api/chat` 依赖 HTTP 请求和 SSE，不适合飞书事件直接调用。  
建议抽一个函数（比如 `generate_reply_for_user(...)`）放在 service 层，返回完整文本字符串。

复用你现在这几段逻辑：

- 建/取会话
- 保存用户消息
- 拉历史
- 调 `azure_openai.stream_chat(...)` 聚合 token
- 保存 assistant 消息、更新标题、写 memory

---

### 5) 飞书事件到本地用户/会话的映射

最小可用：

- 固定映射到一个本地账号（比如 `feishu_bot_user`）

建议版（更安全）：

- 新表 `feishu_bindings`：`open_id -> user_id`
- 新表 `feishu_conversation_map`：`(chat_id, open_id) -> conversation_id`

这样飞书里同一个人会持续在同一会话，不会每条都新建。

---

### 6) 安全控制（必须）

- **验签/解密**：按飞书长连接事件规范校验（如果启用了加密）
- **去重**：存 `event_id`，重复事件直接丢弃
- **回环保护**：忽略机器人自身消息
- **输入限制**：超长截断、空消息过滤、仅处理文本
- **频控**：同一用户每分钟 N 条，超限返回提示

---

### 7) 配置项建议新增

在你现有 `Settings` 基础上增加（名字可自定）：

- `feishu_event_enabled`（开关）
- `feishu_encrypt_key`（如果开了加密）
- `feishu_event_allow_chat_ids`（白名单，可选）

`app_id/app_secret` 你已经有了（`backend/app/config.py` 里已有）。

---

### 8) 本机运行注意事项（桌面版特有）

- 应用必须保持运行，长连接才能收消息
- Mac 睡眠时连接会断，需要自动重连
- 网络切换（Wi-Fi 切换）后要做重连
- 建议加“连接状态日志/托盘状态”

---

## 最小可跑通里程碑（建议按这个顺序）

1. 先连上长连接，打印“已收到事件类型”
2. 收到文本消息时固定回复“收到”
3. 接入你现有 LLM 生成回复
4. 再加会话映射、去重、频控

---

如果你要，我下一条可以给你一份**贴你仓库结构的伪代码骨架**（`feishu_event_client.py` + `main.py` 生命周期调用 + 对话编排函数签名），你基本按着填就能开工。

---

**User**

我不理解，长链接怎么到我的mac上，我的mac没有公网ip啊

---

**Cursor**

关键点是：**长连接是你主动发起“出站连接”**，不是外网主动“入站访问”你的 Mac。  
所以你没有公网 IP 也没关系。

---

### 用白话解释

- **Webhook 模式**：飞书要“打电话进来”到你家门口（需要公网地址）  
- **长连接模式**：你先“打电话给飞书并保持不挂断”，飞书有事就在这通电话里告诉你

你的 Mac 只要能正常上网（像访问网页那样出网），就能建立这条连接。

---

### 为什么 NAT/无公网IP 也可以

家庭网络通常是 NAT：

- 入站：外面直接访问你机器，默认不通（所以 webhook 不行）
- 出站：你访问外网服务，默认可以（所以长连接可行）

长连接本质是 `Mac -> 飞书服务器` 的持续 TCP/TLS 连接。  
飞书事件“回推”走的是这条已建立连接的数据流，不需要再新建到你 Mac 的入站连接。

---

### 现实限制（你要注意）

- 你的应用必须在线运行，断网/睡眠就收不到
- 需要自动重连（网络抖动、切 Wi-Fi、系统休眠）
- 企业网络若限制 WebSocket/长连接端口，可能连不上（可用代理）

---

### 一句话结论

**没公网 IP 完全不妨碍方案A。**  
只要你的 Mac 能主动连到飞书开放平台，飞书就能把消息通过这条长连接送到你本机。

---

**User**

长链接安全吗

---

**Cursor**

安全，但前提是你按规范做。  
**长连接并不天然不安全**，它通常比“暴露公网 webhook”更省暴露面，因为你不需要开入站端口。

## 安全性结论（简版）

- **网络面**：你是出站连接到飞书，攻击面小于公网 webhook
- **协议面**：走 TLS，加上平台签名/加密校验，可防伪造
- **业务面**：真正风险在“你怎么处理事件”，不是长连接本身

## 主要风险与防护

- **伪造事件**：做签名校验/解密校验，失败直接丢弃
- **重放攻击**：校验时间窗 + `event_id` 去重
- **消息洪泛**：用户级限流、全局限流、队列长度保护
- **机器人自循环**：忽略 bot 自己发的消息
- **越权触发**：只允许白名单 chat/user，或做组织内校验
- **敏感泄露**：密钥只放服务端配置，不打到日志
- **提示词攻击**：对“可触发高风险工具”的指令做二次约束（比如发消息/写文档）

## 你这个项目里最该先加的 5 条

- 事件去重表（`event_id` 唯一键）
- 消息来源过滤（只处理 `im.message.receive_v1` 且文本）
- bot 自消息过滤
- 每用户频控（例如 30 秒内最多 N 次）
- 全链路审计日志（但打码 token/secret）

一句话：**长连接可以做得很安全，关键是验签、去重、限流、最小权限这四件事做到位。**

