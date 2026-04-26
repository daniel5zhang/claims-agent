"""
方案管理接口全量测试
覆盖: 获取、确认、取消、调整、根据对话查询、状态流转、异常场景
"""
import pytest


class TestSchemeGet:
    """TC-SCHEME-GET: 获取方案"""

    def test_get_scheme_exists(self, client, sample_scheme):
        """TC-SCHEME-001: 获取存在的方案详情"""
        resp = client.get(f"/api/scheme/{sample_scheme.id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == sample_scheme.id
        assert data["scheme_name"] == "测试方案A"
        assert "service_list" in data
        assert data["status"] == "draft"

    def test_get_scheme_not_found(self, client):
        """TC-SCHEME-002: 获取不存在的方案，返回 404"""
        resp = client.get("/api/scheme/99999")
        assert resp.status_code == 404

    def test_get_scheme_invalid_id(self, client):
        """TC-SCHEME-003: 无效 ID 返回 422"""
        resp = client.get("/api/scheme/abc")
        assert resp.status_code == 422

    def test_get_scheme_service_list_structure(self, client, sample_scheme):
        """TC-SCHEME-004: service_list 结构正确"""
        resp = client.get(f"/api/scheme/{sample_scheme.id}")
        svc_list = resp.json()["data"]["service_list"]
        assert len(svc_list) == 2
        assert svc_list[0]["service_name"] == "图文问诊"
        assert "times" in svc_list[0]
        assert "price" in svc_list[0]

    def test_get_scheme_total_cost_quote(self, client, sample_scheme):
        """TC-SCHEME-005: 总成本和总报价正确"""
        resp = client.get(f"/api/scheme/{sample_scheme.id}")
        data = resp.json()["data"]
        assert data["total_cost"] == 40
        assert data["total_quote"] == 55


class TestSchemeConfirm:
    """TC-SCHEME-CONFIRM: 确认/取消方案"""

    def test_confirm_scheme_success(self, client, sample_scheme):
        """TC-SCHEME-006: 确认草稿方案"""
        resp = client.post(
            f"/api/scheme/{sample_scheme.id}/confirm",
            json={"scheme_id": sample_scheme.id, "confirmed": True}
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "confirmed"
        assert "已确认" in data["message"]

    def test_cancel_confirm_scheme(self, client, sample_scheme):
        """TC-SCHEME-007: 取消已确认的方案"""
        # 先确认
        client.post(f"/api/scheme/{sample_scheme.id}/confirm", json={"scheme_id": sample_scheme.id, "confirmed": True})
        # 再取消
        resp = client.post(
            f"/api/scheme/{sample_scheme.id}/confirm",
            json={"scheme_id": sample_scheme.id, "confirmed": False}
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "draft"

    def test_confirm_not_found(self, client):
        """TC-SCHEME-008: 确认不存在的方案，返回 404"""
        resp = client.post("/api/scheme/99999/confirm", json={"scheme_id": 99999, "confirmed": True})
        assert resp.status_code == 404

    def test_confirm_missing_confirmed_field(self, client, sample_scheme):
        """TC-SCHEME-009: 缺少 confirmed 字段返回 422"""
        resp = client.post(f"/api/scheme/{sample_scheme.id}/confirm", json={"scheme_id": sample_scheme.id})
        assert resp.status_code == 422

    def test_confirm_scheme_id_mismatch(self, client, sample_scheme):
        """TC-SCHEME-010: URL scheme_id 和 body scheme_id 不一致（应允许）"""
        resp = client.post(
            f"/api/scheme/{sample_scheme.id}/confirm",
            json={"scheme_id": sample_scheme.id + 1, "confirmed": True}
        )
        # 当前实现以 URL 为准，所以应该成功
        assert resp.status_code == 200

    def test_reconfirm_already_confirmed(self, client, confirmed_scheme):
        """TC-SCHEME-011: 重复确认已确认方案"""
        resp = client.post(
            f"/api/scheme/{confirmed_scheme.id}/confirm",
            json={"scheme_id": confirmed_scheme.id, "confirmed": True}
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "confirmed"


class TestSchemeAdjust:
    """TC-SCHEME-ADJUST: 调整方案"""

    def test_adjust_draft_scheme(self, client, sample_scheme):
        """TC-SCHEME-012: 调整草稿方案"""
        resp = client.post(
            f"/api/scheme/{sample_scheme.id}/adjust",
            json={"scheme_id": sample_scheme.id, "adjustment_prompt": "增加购药金服务"}
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "message" in data

    def test_adjust_confirmed_scheme_fails(self, client, confirmed_scheme):
        """TC-SCHEME-013: 调整已确认方案应失败"""
        resp = client.post(
            f"/api/scheme/{confirmed_scheme.id}/adjust",
            json={"scheme_id": confirmed_scheme.id, "adjustment_prompt": "增加服务"}
        )
        assert resp.status_code == 400

    def test_adjust_not_found(self, client):
        """TC-SCHEME-014: 调整不存在的方案，返回 404"""
        resp = client.post("/api/scheme/99999/adjust", json={"scheme_id": 99999, "adjustment_prompt": "测试"})
        assert resp.status_code == 404

    def test_adjust_missing_prompt(self, client, sample_scheme):
        """TC-SCHEME-015: 缺少 adjustment_prompt 返回 422"""
        resp = client.post(f"/api/scheme/{sample_scheme.id}/adjust", json={"scheme_id": sample_scheme.id})
        assert resp.status_code == 422

    def test_adjust_empty_prompt(self, client, sample_scheme):
        """TC-SCHEME-016: 空调整提示应正常处理"""
        resp = client.post(
            f"/api/scheme/{sample_scheme.id}/adjust",
            json={"scheme_id": sample_scheme.id, "adjustment_prompt": ""}
        )
        # 空字符串可能通过验证也可能不通过，取决于 Pydantic 配置
        assert resp.status_code in [200, 422]


class TestSchemeByConversation:
    """TC-SCHEME-CONV: 根据对话查询方案"""

    def test_get_scheme_by_conversation_exists(self, client, sample_scheme):
        """TC-SCHEME-017: 根据对话 ID 获取方案"""
        resp = client.get(f"/api/scheme/conversation/{sample_scheme.conversation_id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data is not None
        assert data["id"] == sample_scheme.id

    def test_get_scheme_by_conversation_not_found(self, client):
        """TC-SCHEME-018: 不存在的对话 ID 返回 null"""
        resp = client.get("/api/scheme/conversation/99999")
        assert resp.status_code == 200
        assert resp.json()["data"] is None

    def test_get_scheme_by_conversation_multiple(self, client, db_session):
        """TC-SCHEME-019: 同一对话多个方案，返回最新"""
        from database import GeneratedScheme
        conv_id = 100
        s1 = GeneratedScheme(conversation_id=conv_id, scheme_name="旧方案", service_list_json="[]", status="draft")
        s2 = GeneratedScheme(conversation_id=conv_id, scheme_name="新方案", service_list_json="[]", status="draft")
        db_session.add(s1)
        db_session.add(s2)
        db_session.commit()
        db_session.refresh(s2)

        resp = client.get(f"/api/scheme/conversation/{conv_id}")
        assert resp.status_code == 200
        assert resp.json()["data"]["scheme_name"] == "新方案"

    def test_get_scheme_by_conversation_invalid_id(self, client):
        """TC-SCHEME-020: 无效对话 ID 返回 422"""
        resp = client.get("/api/scheme/conversation/abc")
        assert resp.status_code == 422


class TestSchemeStatusTransition:
    """TC-SCHEME-STATE: 状态流转"""

    def test_draft_to_confirmed(self, client, sample_scheme):
        """TC-SCHEME-021: draft -> confirmed"""
        assert sample_scheme.status == "draft"
        resp = client.post(f"/api/scheme/{sample_scheme.id}/confirm", json={"scheme_id": sample_scheme.id, "confirmed": True})
        assert resp.json()["data"]["status"] == "confirmed"

    def test_confirmed_to_draft(self, client, confirmed_scheme):
        """TC-SCHEME-022: confirmed -> draft"""
        assert confirmed_scheme.status == "confirmed"
        resp = client.post(f"/api/scheme/{confirmed_scheme.id}/confirm", json={"scheme_id": confirmed_scheme.id, "confirmed": False})
        assert resp.json()["data"]["status"] == "draft"

    def test_draft_to_confirmed_to_draft(self, client, sample_scheme):
        """TC-SCHEME-023: draft -> confirmed -> draft -> confirmed"""
        sid = sample_scheme.id
        client.post(f"/api/scheme/{sid}/confirm", json={"scheme_id": sid, "confirmed": True})
        client.post(f"/api/scheme/{sid}/confirm", json={"scheme_id": sid, "confirmed": False})
        resp = client.post(f"/api/scheme/{sid}/confirm", json={"scheme_id": sid, "confirmed": True})
        assert resp.json()["data"]["status"] == "confirmed"
