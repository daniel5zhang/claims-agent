"""
钉钉 Stream 客户端
- Stream 连接管理和消息分发
- 在后台线程中运行 start_forever()，不阻塞 FastAPI 主事件循环
"""
import asyncio
import logging
import re
import threading
from typing import Optional

import dingtalk_stream
from dingtalk_stream import AckMessage

from config import DINGTALK_CLIENT_ID, DINGTALK_CLIENT_SECRET, DINGTALK_ENABLED
from services.dingtalk_service import DingtalkService

logger = logging.getLogger("dingtalk_stream_client")


class ChatbotHandler(dingtalk_stream.ChatbotHandler):
    """钉钉机器人消息处理器"""

    def __init__(self, service: DingtalkService, loop: asyncio.AbstractEventLoop):
        super().__init__()
        self.service = service
        self.loop = loop

    def _get_attr(self, obj, *names):
        """按优先级尝试获取对象属性（支持 snake_case / camelCase）"""
        for name in names:
            val = getattr(obj, name, None)
            if val is not None:
                return val
        return None

    async def process(self, callback: dingtalk_stream.CallbackMessage):
        """异步回调：解析消息并调度到业务层异步处理"""
        try:
            callback_topic = getattr(callback, "topic", None) or ""
            callback_type = getattr(callback, "type", None) or ""
            incoming_message = dingtalk_stream.ChatbotMessage.from_dict(callback.data)

            # 提取关键字段（兼容多种命名风格）
            sender_staff_id = (
                self._get_attr(incoming_message, "sender_staff_id", "senderStaffId") or ""
            )
            conversation_id = (
                self._get_attr(
                    incoming_message,
                    "conversation_id",
                    "conversationId",
                    "open_conversation_id",
                    "openConversationId",
                )
                or ""
            )
            conversation_type = (
                self._get_attr(
                    incoming_message, "conversation_type", "conversationType"
                )
                or "1"
            )
            session_webhook = (
                self._get_attr(
                    incoming_message, "session_webhook", "sessionWebhook"
                )
                or ""
            )
            sender_nick = (
                self._get_attr(incoming_message, "sender_nick", "senderNick") or ""
            )
            chatbot_user_id = (
                self._get_attr(
                    incoming_message, "chatbot_user_id", "chatbotUserId"
                )
                or ""
            )
            message_id = (
                self._get_attr(incoming_message, "msg_id", "msgId", "message_id")
                or ""
            )

            # 解析消息文本
            text_content = ""
            text_obj = getattr(incoming_message, "text", None)
            if text_obj and hasattr(text_obj, "content"):
                text_content = text_obj.content or ""

            # 群聊场景去掉 @机器人 前缀文本
            if conversation_type == "2" and text_content:
                # 钉钉 @ 格式：@机器人名称 或 @机器人名称\u2005（零宽空格）
                # 同时去除 @机器人名称 后可能残留的尾部空格
                text_content = re.sub(
                    r'@[\w\u4e00-\u9fff]+\s*[\u2005]?\s*', '', text_content
                ).strip()

            if not text_content:
                logger.info(
                    f"[ChatbotHandler] 空消息，跳过. sender={sender_staff_id}"
                )
                return AckMessage.STATUS_OK, "OK"

            # 构建消息对象
            from models.dingtalk_schemas import DingtalkMessage

            msg = DingtalkMessage(
                sender_staff_id=sender_staff_id,
                conversation_id=conversation_id,
                conversation_type=conversation_type,
                text_content=text_content,
                session_webhook=session_webhook,
                sender_nick=sender_nick,
                chatbot_user_id=chatbot_user_id,
            )

            logger.info(
                f"[ChatbotHandler] 收到消息: topic={callback_topic}, type={callback_type}, "
                f"msg_id={message_id}, sender={sender_staff_id}, "
                f"nick={sender_nick}, "
                f"type={'单聊' if conversation_type == '1' else '群聊'}, "
                f"content={text_content[:50]}..."
            )

            # 调度异步处理到 FastAPI 主事件循环
            coro = self.service.handle_message(msg)
            asyncio.run_coroutine_threadsafe(coro, self.loop)

            return AckMessage.STATUS_OK, "OK"

        except Exception as e:
            logger.error(f"[ChatbotHandler] 处理消息异常: {e}", exc_info=True)
            return AckMessage.STATUS_OK, "OK"


class DingtalkStreamClient:
    """钉钉 Stream 连接管理器"""

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        self.loop = loop or asyncio.get_event_loop()
        self.service = DingtalkService()
        self.client: Optional[dingtalk_stream.DingTalkStreamClient] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._enabled = (
            DINGTALK_ENABLED and DINGTALK_CLIENT_ID and DINGTALK_CLIENT_SECRET
        )

    def start(self):
        """在后台线程启动 Stream 连接"""
        if not self._enabled:
            logger.info(
                "[DingtalkStreamClient] 钉钉集成未启用或配置不完整，跳过启动"
            )
            return

        if self._thread and self._thread.is_alive():
            logger.warning("[DingtalkStreamClient] Stream 客户端已在运行")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("[DingtalkStreamClient] Stream 客户端已启动")

    def _run(self):
        """线程入口：创建并运行 Stream 客户端"""
        try:
            client_id_suffix = (
                DINGTALK_CLIENT_ID[-6:] if isinstance(DINGTALK_CLIENT_ID, str) else ""
            )
            credential = dingtalk_stream.Credential(
                DINGTALK_CLIENT_ID, DINGTALK_CLIENT_SECRET
            )
            self.client = dingtalk_stream.DingTalkStreamClient(credential)

            handler = ChatbotHandler(self.service, self.loop)

            # 兼容不同版本 SDK 的 TOPIC 定义方式
            topic = getattr(
                dingtalk_stream.chatbot.ChatbotMessage, "TOPIC", "chatbot"
            )
            self.client.register_callback_handler(topic, handler)
            logger.info(
                "[DingtalkStreamClient] 回调注册完成: topic=%s, client_id_suffix=%s, thread=%s",
                topic,
                client_id_suffix,
                threading.current_thread().name,
            )

            logger.info("[DingtalkStreamClient] 开始连接钉钉 Stream...")
            self.client.start_forever()
        except Exception as e:
            logger.error(
                f"[DingtalkStreamClient] Stream 连接异常: {e}", exc_info=True
            )

    def stop(self):
        """优雅关闭 Stream 连接"""
        if self.client:
            try:
                self.client.stop()
                logger.info("[DingtalkStreamClient] Stream 客户端已停止")
            except Exception as e:
                logger.warning(
                    f"[DingtalkStreamClient] 停止客户端异常: {e}"
                )

        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                logger.warning(
                    "[DingtalkStreamClient] Stream 线程未在 5s 内结束"
                )
