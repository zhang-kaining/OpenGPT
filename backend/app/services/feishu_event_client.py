import asyncio
import json
import logging
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


def _extract_text_from_content(raw_content: str) -> str:
    """从飞书消息 content JSON 中提取 text 文本。"""
    text = (raw_content or "").strip()
    if not text:
        return ""
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return str(parsed.get("text") or "").strip()
    except Exception:
        pass
    return text


def _schedule_event_processing(data) -> None:
    """在当前上下文安全调度异步事件处理。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(_process_im_message_event(data))
        return
    loop.create_task(_process_im_message_event(data))


async def _process_im_message_event(data) -> None:
    """
    处理飞书消息事件：
    1) 解析文本消息
    2) 调用现有后端对话链路生成回复
    3) 回发到原会话
    """
    from app.services import azure_openai as oai_service
    from app.services import feishu as feishu_service
    from app.services import memory as mem_service

    if not hasattr(data, "event"):
        return
    event = data.event
    message = event.message if hasattr(event, "message") else None
    if not message:
        return

    message_type = str(getattr(message, "message_type", "") or "").strip().lower()
    if message_type != "text":
        logger.info("跳过非文本消息: type=%s", message_type or "(empty)")
        return

    sender = event.sender if hasattr(event, "sender") else None
    sender_type = str(getattr(sender, "sender_type", "") or "").strip().lower()
    if sender_type and sender_type != "user":
        logger.info("跳过非用户消息: sender_type=%s", sender_type)
        return

    sender_id = getattr(sender, "sender_id", None)
    sender_open_id = str(getattr(sender_id, "open_id", "") or "").strip()
    if not sender_open_id:
        logger.warning("消息缺少发送者 open_id，跳过处理")
        return

    chat_id = str(getattr(message, "chat_id", "") or "").strip()
    if not chat_id:
        logger.warning("消息缺少 chat_id，无法回发")
        return

    raw_content = str(getattr(message, "content", "") or "")
    user_text = _extract_text_from_content(raw_content)
    if not user_text:
        logger.info("空文本消息，跳过")
        return

    user_id = f"feishu:{sender_open_id}"
    memories = mem_service.search_memories(user_text, user_id)
    messages = [{"role": "user", "content": user_text}]

    reply = ""
    async for ev in oai_service.stream_chat(messages, memories, enable_search=False):
        if ev.get("type") == "token":
            reply += ev.get("content", "")
        elif ev.get("type") == "error":
            logger.error("LLM 处理飞书消息失败: %s", ev.get("message", "unknown"))

    reply = (reply or "").strip()
    if not reply:
        reply = "我收到了你的消息，但暂时没生成有效回复。请稍后再试。"

    result = await feishu_service.send_message(reply, receive_id=chat_id)
    if not result.get("success"):
        logger.error("飞书回复发送失败: %s", result.get("error", "unknown"))
        return

    mem_service.add_memories(
        [{"role": "user", "content": user_text}, {"role": "assistant", "content": reply}],
        user_id,
    )
    logger.info("飞书消息处理完成并已回发: chat_id=%s", chat_id)


def _run_feishu_ws_client(log_level: str = "INFO"):
    """在独立进程中运行飞书 WebSocket 客户端"""
    import lark_oapi as lark
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    settings = get_settings()
    app_id = (settings.feishu_app_id or "").strip()
    app_secret = (settings.feishu_app_secret or "").strip()
    if not app_id or not app_secret:
        logger.warning("未配置飞书 app_id 或 app_secret，子进程退出")
        return

    def handle_message_received(data):
        logger.info("=" * 60)
        logger.info("🎉 收到飞书消息事件！")
        logger.info("=" * 60)
        logger.info(f"原始数据: {lark.JSON.marshal(data)}")
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
                    
                    logger.info(f"📨 消息ID: {message_id}")
                    logger.info(f"💬 会话ID: {chat_id}")
                    logger.info(f"👤 发送者ID: {sender_id}")
                    logger.info(f"📝 消息内容: {content}")
                    _schedule_event_processing(data)
        except Exception as e:
            logger.error(f"处理飞书消息事件失败: {e}", exc_info=True)

    def handle_message_read(_data):
        # 已读回执事件不参与业务处理，注册空处理器避免 SDK 报 processor not found。
        logger.debug("收到 message_read 事件（已忽略）")
    
    event_handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(handle_message_received) \
        .register_p2_im_message_message_read_v1(handle_message_read) \
        .build()
    
    ws_client = lark.ws.Client(
        app_id,
        app_secret,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO
    )
    
    logger.info("正在建立飞书长连接...")
    ws_client.start()


class FeishuEventClient:
    """飞书长连接事件客户端，用于接收飞书事件"""

    def __init__(self):
        self._process: Optional = None
        self._running = False

    async def start(self):
        """启动飞书长连接事件客户端"""
        if self._running:
            logger.warning("飞书事件客户端已经在运行")
            return

        settings = get_settings()
        if not settings.feishu_app_id or not settings.feishu_app_secret:
            logger.warning("未配置飞书 app_id 或 app_secret，跳过启动飞书事件客户端")
            return

        try:
            import multiprocessing

            logger.info("正在初始化飞书事件客户端...")
            
            self._process = multiprocessing.Process(target=_run_feishu_ws_client, daemon=True)
            
            self._process.start()
            
            await asyncio.sleep(2)
            
            if self._process.is_alive():
                self._running = True
                logger.info("✅ 飞书长连接事件客户端已启动")
                logger.info("   等待飞书消息事件...")
            else:
                logger.error("❌ 飞书长连接启动失败")
            
        except ImportError as e:
            logger.error("飞书 SDK 未安装，请运行: pip install lark-oapi")
            logger.error(f"ImportError: {e}")
        except Exception as e:
            logger.error(f"启动飞书事件客户端失败: {e}", exc_info=True)

    async def stop(self):
        """停止飞书长连接事件客户端"""
        if not self._running:
            return

        logger.info("正在停止飞书事件客户端...")
        self._running = False

        if self._process and self._process.is_alive():
            try:
                self._process.terminate()
                self._process.join(timeout=5)
                if self._process.is_alive():
                    self._process.kill()
                    self._process.join()
            except Exception as e:
                logger.error(f"关闭飞书客户端时出错: {e}")

        logger.info("飞书事件客户端已停止")

    def is_running(self) -> bool:
        """检查客户端是否正在运行"""
        return self._running and (self._process is not None and self._process.is_alive())


_client_instance: Optional[FeishuEventClient] = None


def get_feishu_event_client() -> FeishuEventClient:
    """获取飞书事件客户端单例"""
    global _client_instance
    if _client_instance is None:
        _client_instance = FeishuEventClient()
    return _client_instance
