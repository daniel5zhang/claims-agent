"""
钉钉集成单元测试
覆盖: 数据模型、用户ID映射、消息处理、Markdown分段、群聊@前缀去除
"""
import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------- mock dingtalk_stream（确保无论环境是否安装都能 import） ----------
dingtalk_stream_mock = MagicMock()
dingtalk_stream_mock.ChatbotHandler = MagicMock()
dingtalk_stream_mock.ChatbotMessage = MagicMock()
dingtalk_stream_mock.AckMessage.STATUS_OK = "OK"
sys.modules["dingtalk_stream"] = dingtalk_stream_mock

from models.dingtalk_schemas import DingtalkFileInfo, DingtalkMessage, DingtalkReply
from services.dingtalk_service import DingtalkService
from services.dingtalk_stream_client import ChatbotHandler


# ==================== 1. 数据模型测试 ====================

class TestDingtalkSchemas:
    """数据模型测试"""

    def test_dingtalk_message_creation_and_fields(self):
        """测试 DingtalkMessage 创建和字段验证"""
        msg = DingtalkMessage(
            sender_staff_id="user123",
            conversation_id="conv456",
            conversation_type="1",
            text_content="你好",
            session_webhook="https://webhook.example.com",
            sender_nick="张三",
            sender_corp_id="corp789",
            chatbot_user_id="bot001",
        )
        assert msg.sender_staff_id == "user123"
        assert msg.conversation_id == "conv456"
        assert msg.conversation_type == "1"
        assert msg.text_content == "你好"
        assert msg.session_webhook == "https://webhook.example.com"
        assert msg.sender_nick == "张三"
        assert msg.sender_corp_id == "corp789"
        assert msg.chatbot_user_id == "bot001"

    def test_dingtalk_message_optional_defaults(self):
        """测试 DingtalkMessage 可选字段默认为 None"""
        msg = DingtalkMessage(
            sender_staff_id="user123",
            conversation_id="conv456",
            conversation_type="1",
            text_content="测试",
            session_webhook="https://webhook.example.com",
        )
        assert msg.sender_nick is None
        assert msg.sender_corp_id is None
        assert msg.chatbot_user_id is None

    def test_dingtalk_reply_defaults(self):
        """测试 DingtalkReply 默认值和序列化"""
        reply = DingtalkReply()
        assert reply.msgtype == "markdown"
        assert reply.markdown is None
        assert reply.text is None

    def test_dingtalk_reply_serialization(self):
        """测试 DingtalkReply 带数据序列化"""
        reply = DingtalkReply(
            markdown={"title": "测试标题", "text": "测试内容"}
        )
        data = reply.model_dump()
        assert data["msgtype"] == "markdown"
        assert data["markdown"]["title"] == "测试标题"
        assert data["markdown"]["text"] == "测试内容"
        assert data["text"] is None

    def test_dingtalk_file_info_creation(self):
        """测试 DingtalkFileInfo 创建"""
        file_info = DingtalkFileInfo(
            media_id="media123",
            file_name="报价单.xlsx",
            file_type="xlsx",
        )
        assert file_info.media_id == "media123"
        assert file_info.file_name == "报价单.xlsx"
        assert file_info.file_type == "xlsx"


# ==================== 2. 用户ID映射测试 ====================

class TestUserIdMapping:
    """用户ID映射测试"""

    @pytest.fixture
    def service(self):
        with patch("services.dingtalk_service.get_agent_service") as mock_get_agent:
            mock_get_agent.return_value = MagicMock()
            yield DingtalkService()

    def test_single_chat_user_id(self, service):
        """单聊场景：验证 user_id = dingtalk_{senderStaffId}"""
        msg = DingtalkMessage(
            sender_staff_id="staff_abc",
            conversation_id="conv_123",
            conversation_type="1",
            text_content="你好",
            session_webhook="https://webhook.example.com",
        )
        user_id = service._build_user_id(msg)
        assert user_id == "dingtalk_staff_abc"

    def test_group_chat_user_id(self, service):
        """群聊场景：验证 user_id = dingtalk_group_{conversationId}_{senderStaffId}"""
        msg = DingtalkMessage(
            sender_staff_id="staff_abc",
            conversation_id="conv_123",
            conversation_type="2",
            text_content="你好",
            session_webhook="https://webhook.example.com",
        )
        user_id = service._build_user_id(msg)
        assert user_id == "dingtalk_group_conv_123_staff_abc"


# ==================== 3. 消息处理测试 ====================

class TestMessageProcessing:
    """消息处理测试（Mock agent_service）"""

    @pytest.fixture
    def service(self):
        with patch("services.dingtalk_service.get_agent_service") as mock_get_agent:
            mock_agent = MagicMock()
            mock_get_agent.return_value = mock_agent
            yield DingtalkService()

    @pytest.fixture
    def sample_message(self):
        return DingtalkMessage(
            sender_staff_id="staff_abc",
            conversation_id="conv_123",
            conversation_type="1",
            text_content="你好",
            session_webhook="https://webhook.example.com",
        )

    def test_handle_message_normal(self, service, sample_message):
        """Mock process_message 返回正常结果，验证 Markdown 格式化"""
        mock_result = {
            "session_id": "sess_abc_123",
            "message": {"role": "assistant", "content": "您好，有什么可以帮您？"},
            "scheme": None,
        }

        with patch.object(
            service.agent, "process_message", new_callable=AsyncMock, return_value=mock_result
        ):
            with patch.object(
                service, "_send_markdown_reply", new_callable=AsyncMock
            ) as mock_send:
                with patch("services.dingtalk_service.SessionLocal") as mock_session_local:
                    mock_db = MagicMock()
                    mock_session_local.return_value = mock_db

                    asyncio.run(service.handle_message(sample_message))

                    mock_send.assert_awaited_once_with(
                        sample_message.session_webhook,
                        "您好，有什么可以帮您？",
                    )
                    assert (
                        asyncio.run(
                            service._get_session_id("dingtalk_staff_abc")
                        )
                        == "sess_abc_123"
                    )

    def test_handle_message_with_confirmed_scheme(self, service, sample_message):
        """Mock process_message 返回含已确认方案的结果，验证方案检测逻辑"""
        mock_result = {
            "session_id": "sess_abc_123",
            "message": {"role": "assistant", "content": "方案已生成"},
            "scheme": {"id": 42, "status": "confirmed"},
        }

        with patch.object(
            service.agent, "process_message", new_callable=AsyncMock, return_value=mock_result
        ):
            with patch.object(
                service, "_send_markdown_reply", new_callable=AsyncMock
            ) as mock_send:
                with patch.object(
                    service, "_handle_confirmed_scheme", new_callable=AsyncMock
                ) as mock_handle:
                    with patch("services.dingtalk_service.SessionLocal") as mock_session_local:
                        mock_db = MagicMock()
                        mock_session_local.return_value = mock_db

                        asyncio.run(service.handle_message(sample_message))

                        mock_send.assert_awaited_once_with(
                            sample_message.session_webhook,
                            "方案已生成",
                        )
                        mock_handle.assert_awaited_once_with(
                            mock_db, sample_message, mock_result["scheme"]
                        )

    def test_handle_message_exception(self, service, sample_message):
        """Mock process_message 抛出异常，验证错误处理"""
        with patch.object(
            service.agent,
            "process_message",
            new_callable=AsyncMock,
            side_effect=Exception("LLM service error"),
        ):
            with patch.object(
                service, "_send_markdown_reply", new_callable=AsyncMock
            ) as mock_send:
                with patch("services.dingtalk_service.SessionLocal") as mock_session_local:
                    mock_db = MagicMock()
                    mock_session_local.return_value = mock_db

                    asyncio.run(service.handle_message(sample_message))

                    mock_send.assert_awaited_once_with(
                        sample_message.session_webhook,
                        "抱歉，服务暂时出现异常，请稍后重试。如问题持续，请联系技术支持。",
                    )


# ==================== 4. Markdown 分段测试 ====================

class TestMarkdownSplit:
    """Markdown 分段测试"""

    def test_short_message_no_split(self):
        """短消息不分段"""
        text = "这是一个短消息，不需要分段"
        chunks = DingtalkService._split_text(text, 20000)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_message_split(self):
        """超长消息（>20000字符）正确分段"""
        lines = [f"这是第{i:04d}行内容，包含一些测试数据和填充字符用于增加行长度" for i in range(1000)]
        text = "\n".join(lines)
        assert len(text) > 20000

        chunks = DingtalkService._split_text(text, 20000)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 20000

    def test_split_not_in_middle_of_line(self):
        """分段不会在行中间截断"""
        lines = [f"line_{i:05d}_完整行内容不被截断" for i in range(1000)]
        text = "\n".join(lines)

        chunks = DingtalkService._split_text(text, 20000)

        # 重建所有行并验证与原始一致
        original_lines = text.split("\n")
        reconstructed_lines = []
        for chunk in chunks:
            reconstructed_lines.extend(chunk.split("\n"))

        assert reconstructed_lines == original_lines


# ==================== 5. 群聊 @机器人 前缀去除测试 ====================

class TestAtPrefixRemoval:
    """群聊 @机器人 前缀去除测试"""

    @pytest.fixture
    def service(self):
        with patch("services.dingtalk_service.get_agent_service") as mock_get_agent:
            mock_get_agent.return_value = MagicMock()
            yield DingtalkService()

    def _make_handler(self, service):
        loop = MagicMock()
        handler = ChatbotHandler(service, loop)
        return handler, loop

    def _make_mock_incoming_message(self, text_content, conversation_type="2"):
        """构造 mock ChatbotMessage 对象"""
        mock_msg = MagicMock()
        mock_msg.sender_staff_id = "staff_abc"
        mock_msg.conversation_id = "conv_123"
        mock_msg.conversation_type = conversation_type
        mock_msg.session_webhook = "https://webhook.example.com"
        mock_msg.sender_nick = "张三"
        mock_msg.chatbot_user_id = "bot001"

        text_obj = MagicMock()
        text_obj.content = text_content
        mock_msg.text = text_obj
        return mock_msg

    def _run_handler(self, handler, callback, mock_msg, mock_msg_cls_patch):
        """统一运行 handler.process 并返回捕获的 DingtalkMessage 参数"""
        def _consume_coro(coro, _loop):
            # 测试中 mock 掉 run_coroutine_threadsafe 后，显式关闭协程，
            # 避免 "coroutine was never awaited" 警告
            try:
                coro.close()
            except Exception:
                pass
            return MagicMock()

        with patch("services.dingtalk_stream_client.dingtalk_stream") as mock_ds:
            mock_ds.ChatbotMessage.from_dict.return_value = mock_msg
            with patch(
                "services.dingtalk_stream_client.asyncio.run_coroutine_threadsafe",
                side_effect=_consume_coro,
            ):
                with mock_msg_cls_patch as mock_msg_cls:
                    status, msg = asyncio.run(handler.process(callback))
                    assert status == "OK"
                    assert mock_msg_cls.called
                    return mock_msg_cls.call_args.kwargs

    def test_remove_at_bot_prefix_simple(self, service):
        """验证 '@机器人名称 你好' 正确提取为 '你好'"""
        handler, _ = self._make_handler(service)
        callback = MagicMock()
        callback.data = {}
        mock_msg = self._make_mock_incoming_message("@方案助手 你好")

        call_kwargs = self._run_handler(
            handler, callback, mock_msg,
            patch("models.dingtalk_schemas.DingtalkMessage")
        )
        assert call_kwargs["text_content"] == "你好"

    def test_remove_at_bot_prefix_with_zero_width_space(self, service):
        """验证 '@机器人名称\u2005你好'（含零宽空格）正确提取"""
        handler, _ = self._make_handler(service)
        callback = MagicMock()
        callback.data = {}
        mock_msg = self._make_mock_incoming_message("@方案助手\u2005请帮我生成一个报价")

        call_kwargs = self._run_handler(
            handler, callback, mock_msg,
            patch("models.dingtalk_schemas.DingtalkMessage")
        )
        assert call_kwargs["text_content"] == "请帮我生成一个报价"

    def test_remove_at_bot_prefix_with_extra_spaces(self, service):
        """验证 '@机器人名称   你好'（多空格）正确提取"""
        handler, _ = self._make_handler(service)
        callback = MagicMock()
        callback.data = {}
        mock_msg = self._make_mock_incoming_message("@方案助手   你好")

        call_kwargs = self._run_handler(
            handler, callback, mock_msg,
            patch("models.dingtalk_schemas.DingtalkMessage")
        )
        assert call_kwargs["text_content"] == "你好"

    def test_no_prefix_unaffected(self, service):
        """验证无前缀的消息不受影响"""
        handler, _ = self._make_handler(service)
        callback = MagicMock()
        callback.data = {}
        mock_msg = self._make_mock_incoming_message("你好，直接发送的消息")

        call_kwargs = self._run_handler(
            handler, callback, mock_msg,
            patch("models.dingtalk_schemas.DingtalkMessage")
        )
        assert call_kwargs["text_content"] == "你好，直接发送的消息"

    def test_single_chat_no_at_removal(self, service):
        """验证单聊场景不会去除 @前缀"""
        handler, _ = self._make_handler(service)
        callback = MagicMock()
        callback.data = {}
        mock_msg = self._make_mock_incoming_message("@某人 你好", conversation_type="1")

        call_kwargs = self._run_handler(
            handler, callback, mock_msg,
            patch("models.dingtalk_schemas.DingtalkMessage")
        )
        # 单聊场景不应去除 @前缀
        assert call_kwargs["text_content"] == "@某人 你好"
