"""
端到端全流程测试
覆盖: 完整业务流、异常分支、状态流转
"""
import pytest


class TestCompleteFlow:
    """TC-FLOW-COMPLETE: 完整业务流程"""

    def test_flow_chat_to_manual(self, client, sample_services, sample_manual_template):
        """TC-FLOW-001: 对话 -> 方案 -> 确认 -> 手册 完整流程"""
        # 1. 开始对话
        r1 = client.post("/api/chat/send", json={"message": "我想做一个企业健管方案"})
        assert r1.status_code == 200
        sid = r1.json()["data"]["session_id"]

        # 2. 继续对话（模拟多轮）
        r2 = client.post("/api/chat/send", json={"session_id": sid, "message": "预算50元，针对40岁以上人群"})
        assert r2.status_code == 200

        # 3. 获取对话历史
        r3 = client.get(f"/api/chat/history/{sid}")
        assert r3.status_code == 200
        assert len(r3.json()["data"]["messages"]) >= 4

        # 4. 根据对话获取方案（如果生成了）
        conv_id = r3.json()["data"].get("messages", [{}])[0].get("conversation_id", 1)
        r4 = client.get(f"/api/scheme/conversation/{conv_id}")
        assert r4.status_code == 200

    def test_flow_create_scheme_directly(self, client, sample_scheme):
        """TC-FLOW-002: 直接操作已有方案"""
        # 获取方案
        r1 = client.get(f"/api/scheme/{sample_scheme.id}")
        assert r1.status_code == 200
        assert r1.json()["data"]["status"] == "draft"

        # 确认方案
        r2 = client.post(f"/api/scheme/{sample_scheme.id}/confirm", json={"scheme_id": sample_scheme.id, "confirmed": True})
        assert r2.status_code == 200
        assert r2.json()["data"]["status"] == "confirmed"

        # 生成手册
        r3 = client.post("/api/manual/generate", json={"scheme_id": sample_scheme.id})
        assert r3.status_code == 200
        manual_id = r3.json()["data"]["manual_id"]

        # 获取手册
        r4 = client.get(f"/api/manual/{manual_id}")
        assert r4.status_code == 200

        # 下载手册
        r5 = client.get(f"/api/manual/{manual_id}/download")
        assert r5.status_code == 200

    def test_flow_adjust_before_confirm(self, client, sample_scheme):
        """TC-FLOW-003: 调整 -> 确认 -> 手册"""
        # 调整方案
        r1 = client.post(f"/api/scheme/{sample_scheme.id}/adjust", json={"scheme_id": sample_scheme.id, "adjustment_prompt": "增加服务"})
        assert r1.status_code == 200

        # 确认
        r2 = client.post(f"/api/scheme/{sample_scheme.id}/confirm", json={"scheme_id": sample_scheme.id, "confirmed": True})
        assert r2.status_code == 200

        # 生成手册
        r3 = client.post("/api/manual/generate", json={"scheme_id": sample_scheme.id})
        assert r3.status_code == 200


class TestExceptionFlow:
    """TC-FLOW-EXCEPT: 异常流程"""

    def test_flow_generate_without_confirm(self, client, sample_scheme):
        """TC-FLOW-004: 未确认直接生成手册失败"""
        r1 = client.post("/api/manual/generate", json={"scheme_id": sample_scheme.id})
        assert r1.status_code == 400
        assert "未确认" in r1.json()["detail"]

    def test_flow_adjust_confirmed_scheme(self, client, confirmed_scheme):
        """TC-FLOW-005: 已确认方案调整失败"""
        r1 = client.post(f"/api/scheme/{confirmed_scheme.id}/adjust", json={"scheme_id": confirmed_scheme.id, "adjustment_prompt": "增加服务"})
        assert r1.status_code == 400

    def test_flow_double_confirm(self, client, sample_scheme):
        """TC-FLOW-006: 重复确认不影响状态"""
        client.post(f"/api/scheme/{sample_scheme.id}/confirm", json={"scheme_id": sample_scheme.id, "confirmed": True})
        r2 = client.post(f"/api/scheme/{sample_scheme.id}/confirm", json={"scheme_id": sample_scheme.id, "confirmed": True})
        assert r2.status_code == 200
        assert r2.json()["data"]["status"] == "confirmed"

    def test_flow_cancel_regenerate(self, client, confirmed_scheme, sample_manual_template):
        """TC-FLOW-007: 取消确认后重新生成手册应失败"""
        # 先生成手册
        r1 = client.post("/api/manual/generate", json={"scheme_id": confirmed_scheme.id})
        assert r1.status_code == 200

        # 取消确认
        client.post(f"/api/scheme/{confirmed_scheme.id}/confirm", json={"scheme_id": confirmed_scheme.id, "confirmed": False})

        # 再次生成应失败
        r3 = client.post("/api/manual/generate", json={"scheme_id": confirmed_scheme.id})
        assert r3.status_code == 400


class TestMaterialIntegration:
    """TC-FLOW-MAT: 素材库集成"""

    def test_flow_search_then_scheme(self, client, sample_services):
        """TC-FLOW-008: 搜索素材 -> 创建方案引用素材"""
        # 搜索
        r1 = client.get("/api/material/services?keyword=问诊")
        assert r1.status_code == 200
        services = r1.json()["data"]
        assert len(services) >= 2

        # 获取分类
        r2 = client.get("/api/material/categories")
        assert r2.status_code == 200
        assert "基础服务" in r2.json()["data"]

        # 获取详情
        svc_id = services[0]["id"]
        r3 = client.get(f"/api/material/services/{svc_id}")
        assert r3.status_code == 200
        assert r3.json()["data"]["name"] == services[0]["name"]

    def test_flow_all_categories_have_services(self, client, sample_services):
        """TC-FLOW-009: 每个类别下都有服务"""
        r1 = client.get("/api/material/categories")
        cats = r1.json()["data"]
        for cat in cats:
            r2 = client.get(f"/api/material/services?category={cat}")
            assert len(r2.json()["data"]) > 0


class TestStateMachine:
    """TC-FLOW-STATE: 状态机验证"""

    def test_scheme_state_transitions(self, client, sample_scheme):
        """TC-FLOW-010: 方案状态转换图"""
        sid = sample_scheme.id
        # draft --confirm--> confirmed
        r1 = client.post(f"/api/scheme/{sid}/confirm", json={"scheme_id": sid, "confirmed": True})
        assert r1.json()["data"]["status"] == "confirmed"

        # confirmed --cancel--> draft
        r2 = client.post(f"/api/scheme/{sid}/confirm", json={"scheme_id": sid, "confirmed": False})
        assert r2.json()["data"]["status"] == "draft"

        # draft --adjust--> draft (可能内容变化)
        r3 = client.post(f"/api/scheme/{sid}/adjust", json={"scheme_id": sid, "adjustment_prompt": "测试调整"})
        assert r3.status_code == 200

        # draft --confirm--> confirmed
        r4 = client.post(f"/api/scheme/{sid}/confirm", json={"scheme_id": sid, "confirmed": True})
        assert r4.json()["data"]["status"] == "confirmed"

    def test_manual_state_after_generation(self, client, confirmed_scheme, sample_manual_template, db_session):
        """TC-FLOW-011: 手册生成后状态为 generated"""
        from database import GeneratedManual
        r1 = client.post("/api/manual/generate", json={"scheme_id": confirmed_scheme.id})
        manual_id = r1.json()["data"]["manual_id"]

        manual = db_session.query(GeneratedManual).filter(GeneratedManual.id == manual_id).first()
        assert manual.status == "generated"
        assert manual.docx_path is not None
