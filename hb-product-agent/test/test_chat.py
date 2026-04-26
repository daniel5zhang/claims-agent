"""
对话接口全量测试
覆盖: 发送消息、流式发送、历史记录、边界条件、异常场景
"""
import pytest


class TestChatSend:
    """TC-CHAT-SEND: 发送消息"""

    def test_send_new_session(self, client):
        """TC-CHAT-001: 新会话发送消息，返回 session_id"""
        resp = client.post("/api/chat/send", json={"message": "你好"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "session_id" in data["data"]
        assert data["data"]["message"]["role"] == "assistant"

    def test_send_with_existing_session(self, client):
        """TC-CHAT-002: 带 session_id 续会话"""
        r1 = client.post("/api/chat/send", json={"message": "你好"})
        sid = r1.json()["data"]["session_id"]
        r2 = client.post("/api/chat/send", json={"session_id": sid, "message": "继续对话"})
        assert r2.status_code == 200
        assert r2.json()["data"]["session_id"] == sid

    def test_send_empty_message(self, client):
        """TC-CHAT-003: 发送空消息，应正常处理（模型返回提示）"""
        resp = client.post("/api/chat/send", json={"message": ""})
        assert resp.status_code == 200

    def test_send_long_message(self, client):
        """TC-CHAT-004: 发送超长消息（500字）"""
        long_msg = "测试" * 250
        resp = client.post("/api/chat/send", json={"message": long_msg})
        assert resp.status_code == 200

    def test_send_special_chars(self, client):
        """TC-CHAT-005: 发送含特殊字符的消息"""
        resp = client.post("/api/chat/send", json={"message": "<>\"'&@#$%^*()_+{}|:"})
        assert resp.status_code == 200

    def test_send_chinese_punctuation(self, client):
        """TC-CHAT-006: 发送含中文标点"""
        resp = client.post("/api/chat/send", json={"message": "你好，我想了解一下：图文问诊、视频问诊的价格。谢谢！"})
        assert resp.status_code == 200

    def test_send_invalid_session_id(self, client):
        """TC-CHAT-007: 使用无效 session_id，应创建新会话"""
        resp = client.post("/api/chat/send", json={"session_id": "invalid_id_12345", "message": "测试"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        # 无效 session_id 会被忽略，创建新会话
        assert "session_id" in data

    def test_send_missing_message_field(self, client):
        """TC-CHAT-008: 缺少 message 字段，返回 422"""
        resp = client.post("/api/chat/send", json={})
        assert resp.status_code == 422

    def test_send_message_type_none(self, client):
        """TC-CHAT-009: message 为 null，返回 422"""
        resp = client.post("/api/chat/send", json={"message": None})
        assert resp.status_code == 422

    def test_send_wrong_content_type(self, client):
        """TC-CHAT-010: Content-Type 错误，返回 422"""
        resp = client.post("/api/chat/send", data="raw text", headers={"Content-Type": "text/plain"})
        assert resp.status_code == 422


class TestChatStream:
    """TC-CHAT-STREAM: 流式发送（当前与非流式等价）"""

    def test_send_stream_returns_data(self, client):
        """TC-CHAT-011: /send-stream 返回正常数据"""
        resp = client.post("/api/chat/send-stream", json={"message": "测试流式"})
        assert resp.status_code == 200
        assert "session_id" in resp.json()["data"]


class TestChatHistory:
    """TC-CHAT-HISTORY: 历史记录"""

    def test_get_history_exists(self, client):
        """TC-CHAT-012: 获取存在的会话历史"""
        r1 = client.post("/api/chat/send", json={"message": "第一条"})
        sid = r1.json()["data"]["session_id"]
        r2 = client.post("/api/chat/send", json={"session_id": sid, "message": "第二条"})

        r3 = client.get(f"/api/chat/history/{sid}")
        assert r3.status_code == 200
        data = r3.json()["data"]
        assert data["session_id"] == sid
        assert len(data["messages"]) >= 4  # user+assistant x2

    def test_get_history_not_found(self, client):
        """TC-CHAT-013: 获取不存在的会话，返回 404"""
        resp = client.get("/api/chat/history/nonexistent123")
        assert resp.status_code == 404

    def test_get_history_empty_session(self, client):
        """TC-CHAT-014: 新建会话后立即获取历史"""
        r1 = client.post("/api/chat/send", json={"message": "你好"})
        sid = r1.json()["data"]["session_id"]
        r2 = client.get(f"/api/chat/history/{sid}")
        assert r2.status_code == 200
        assert len(r2.json()["data"]["messages"]) == 2

    def test_history_contains_extracted_needs(self, client):
        """TC-CHAT-015: 历史包含提取的需求信息"""
        r1 = client.post("/api/chat/send", json={"message": "测试"})
        sid = r1.json()["data"]["session_id"]
        r2 = client.get(f"/api/chat/history/{sid}")
        data = r2.json()["data"]
        assert "extracted_needs" in data

    def test_history_method_post_not_allowed(self, client):
        """TC-CHAT-016: POST /history/{id} 返回 405"""
        resp = client.post("/api/chat/history/test123")
        assert resp.status_code == 405


class TestChatMultiRound:
    """TC-CHAT-MULTI: 多轮对话"""

    def test_multi_round_consistency(self, client):
        """TC-CHAT-017: 多轮对话 session_id 一致"""
        sid = None
        for i in range(3):
            payload = {"message": f"第{i+1}轮消息"}
            if sid:
                payload["session_id"] = sid
            resp = client.post("/api/chat/send", json=payload)
            assert resp.status_code == 200
            if sid is None:
                sid = resp.json()["data"]["session_id"]
            else:
                assert resp.json()["data"]["session_id"] == sid

    def test_history_grows_with_messages(self, client):
        """TC-CHAT-018: 历史记录随消息增长"""
        r1 = client.post("/api/chat/send", json={"message": "开始"})
        sid = r1.json()["data"]["session_id"]

        for msg in ["问题1", "问题2", "问题3"]:
            client.post("/api/chat/send", json={"session_id": sid, "message": msg})

        history = client.get(f"/api/chat/history/{sid}").json()["data"]
        # 开始: 2条, +3轮: 每轮2条 = 8条
        assert len(history["messages"]) >= 8
