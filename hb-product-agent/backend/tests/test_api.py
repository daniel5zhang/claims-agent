"""
API 全覆盖测试用例
"""
import os
os.environ["DB_TYPE"] = "sqlite"  # 测试使用 SQLite 隔离
os.environ["DB_URL"] = "sqlite:///./test.db"

import pytest
import json
from dotenv import load_dotenv
from fastapi.testclient import TestClient

# 加载 .env 配置（包含百炼 API Key）
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(env_path)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sys
sys.path.insert(0, "/Users/daniel/Desktop/code/产品精算/hb-product-agent/backend")

from database import Base, get_db
from main import app

# 测试数据库
TEST_DB_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 覆盖依赖注入
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    # 初始化测试数据（服务素材）
    from data.init_db import _create_sample_services
    db = TestingSessionLocal()
    try:
        _create_sample_services(db)
    finally:
        db.close()
    yield
    Base.metadata.drop_all(bind=engine)


class TestHealth:
    """健康检查接口测试"""

    def test_health_check(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["status"] == "ok"


class TestChat:
    """对话接口测试"""

    def test_send_message_new_session(self):
        """TC001: 新会话发送消息"""
        resp = client.post("/api/chat/send", json={"message": "你好"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "session_id" in data["data"]
        assert data["data"]["message"]["role"] == "assistant"
        self.session_id = data["data"]["session_id"]

    def test_send_message_with_session(self):
        """TC002: 带 session_id 发送消息"""
        # 先创建会话
        resp1 = client.post("/api/chat/send", json={"message": "你好"})
        session_id = resp1.json()["data"]["session_id"]

        # 继续对话
        resp2 = client.post("/api/chat/send", json={
            "session_id": session_id,
            "message": "我想做一个企业健管方案"
        })
        assert resp2.status_code == 200
        data = resp2.json()["data"]
        assert data["session_id"] == session_id

    def test_get_history(self):
        """TC003: 获取对话历史"""
        resp1 = client.post("/api/chat/send", json={"message": "测试历史"})
        session_id = resp1.json()["data"]["session_id"]

        resp2 = client.get(f"/api/chat/history/{session_id}")
        assert resp2.status_code == 200
        data = resp2.json()["data"]
        assert data["session_id"] == session_id
        assert len(data["messages"]) >= 2

    def test_history_not_found(self):
        """TC004: 获取不存在的会话历史"""
        resp = client.get("/api/chat/history/nonexist")
        assert resp.status_code == 404


class TestMaterial:
    """素材库接口测试"""

    def test_list_services(self):
        """TC005: 获取服务素材列表"""
        resp = client.get("/api/material/services")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)

    def test_search_services(self):
        """TC006: 搜索服务素材"""
        resp = client.get("/api/material/services?keyword=心理咨询")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0

    def test_list_categories(self):
        """TC007: 获取服务类别"""
        resp = client.get("/api/material/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)


class TestScheme:
    """方案接口测试"""

    @pytest.fixture
    def scheme_id(self):
        """创建一个测试方案"""
        # 直接创建方案记录（绕过Agent多轮对话，确保测试稳定）
        from database import GeneratedScheme, get_db
        db = next(override_get_db())
        scheme = GeneratedScheme(
            conversation_id=1,
            scheme_name="测试方案",
            service_list_json='[{"name": "图文问诊", "times": "不限次", "price": 10}]',
            total_cost=10,
            total_quote=15,
            status="draft",
        )
        db.add(scheme)
        db.commit()
        db.refresh(scheme)
        scheme_id = scheme.id
        db.close()
        return scheme_id

    def test_get_scheme(self, scheme_id):
        """TC008: 获取方案详情"""
        if not scheme_id:
            pytest.skip("未生成方案")
        resp = client.get(f"/api/scheme/{scheme_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "service_list" in data["data"]

    def test_confirm_scheme(self, scheme_id):
        """TC009: 确认方案"""
        if not scheme_id:
            pytest.skip("未生成方案")
        resp = client.post(f"/api/scheme/{scheme_id}/confirm", json={
            "scheme_id": scheme_id,
            "confirmed": True
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["status"] == "confirmed"

    def test_cancel_confirm(self, scheme_id):
        """TC010: 取消确认方案"""
        if not scheme_id:
            pytest.skip("未生成方案")
        # 先确认
        client.post(f"/api/scheme/{scheme_id}/confirm", json={
            "scheme_id": scheme_id,
            "confirmed": True
        })
        # 再取消
        resp = client.post(f"/api/scheme/{scheme_id}/confirm", json={
            "scheme_id": scheme_id,
            "confirmed": False
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "draft"

    def test_adjust_scheme(self, scheme_id):
        """TC011: 调整方案"""
        if not scheme_id:
            pytest.skip("未生成方案")
        resp = client.post(f"/api/scheme/{scheme_id}/adjust", json={
            "scheme_id": scheme_id,
            "adjustment_prompt": "增加视频问诊"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0

    def test_get_scheme_not_found(self):
        """TC012: 获取不存在的方案"""
        resp = client.get("/api/scheme/99999")
        assert resp.status_code == 404


class TestManual:
    """服务手册接口测试"""

    @pytest.fixture
    def confirmed_scheme_id(self):
        """创建一个已确认的方案"""
        from database import GeneratedScheme
        db = next(override_get_db())
        scheme = GeneratedScheme(
            conversation_id=1,
            scheme_name="测试确认方案",
            service_list_json='[{"name": "图文问诊", "times": "不限次", "price": 10}, {"name": "视频问诊", "times": "2次", "price": 30}]',
            total_cost=40,
            total_quote=55,
            status="confirmed",
        )
        db.add(scheme)
        db.commit()
        db.refresh(scheme)
        scheme_id = scheme.id
        db.close()
        return scheme_id

    def test_generate_manual_success(self, confirmed_scheme_id):
        """TC013: 生成服务手册（方案已确认）"""
        resp = client.post("/api/manual/generate", json={
            "scheme_id": confirmed_scheme_id
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "manual_id" in data["data"]

    def test_generate_manual_not_confirmed(self):
        """TC014: 未确认方案不能生成手册"""
        # 直接创建草稿方案（绕过Agent多轮对话）
        from database import GeneratedScheme
        db = next(override_get_db())
        scheme = GeneratedScheme(
            conversation_id=1,
            scheme_name="草稿方案",
            service_list_json='[{"name": "图文问诊", "times": "不限次", "price": 10}]',
            total_cost=10,
            total_quote=15,
            status="draft",
        )
        db.add(scheme)
        db.commit()
        db.refresh(scheme)
        scheme_id = scheme.id
        db.close()

        resp2 = client.post("/api/manual/generate", json={
            "scheme_id": scheme_id
        })
        assert resp2.status_code == 400
        assert "未确认" in resp2.json()["detail"]

    def test_get_manual_not_found(self):
        """TC015: 获取不存在的手册"""
        resp = client.get("/api/manual/99999")
        assert resp.status_code == 404


class TestFullFlow:
    """全流程集成测试"""

    def test_complete_flow(self):
        """TC016: 完整流程：对话 -> 生成方案 -> 确认 -> 生成手册"""
        # 1. 开始对话
        resp1 = client.post("/api/chat/send", json={
            "message": "我想做一个车险随车赠送的健管服务包，预算30元"
        })
        assert resp1.status_code == 200
        data1 = resp1.json().get("data", {})
        session_id = data1.get("session_id")
        scheme = data1.get("scheme")

        # 2. 调整方案
        if scheme and scheme.get("id"):
            resp2 = client.post(f"/api/scheme/{scheme['id']}/adjust", json={
                "scheme_id": scheme["id"],
                "adjustment_prompt": "增加购药金"
            })
            assert resp2.status_code == 200

        # 3. 确认方案
        if scheme and scheme.get("id"):
            resp3 = client.post(f"/api/scheme/{scheme['id']}/confirm", json={
                "scheme_id": scheme["id"],
                "confirmed": True
            })
            assert resp3.status_code == 200
            assert resp3.json()["data"]["status"] == "confirmed"

            # 4. 生成手册
            resp4 = client.post("/api/manual/generate", json={
                "scheme_id": scheme["id"]
            })
            assert resp4.status_code == 200
            assert "manual_id" in resp4.json()["data"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
