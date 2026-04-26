"""
服务手册接口全量测试
覆盖: 生成、获取、下载、异常场景、状态校验
"""
import os


class TestManualGenerate:
    """TC-MANUAL-GEN: 生成服务手册"""

    def test_generate_confirmed_scheme(self, client, confirmed_scheme, sample_manual_template):
        """TC-MANUAL-001: 已确认方案生成手册"""
        resp = client.post("/api/manual/generate", json={"scheme_id": confirmed_scheme.id})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "manual_id" in data
        assert data["status"] == "generated"
        assert "manual_title" in data

    def test_generate_draft_scheme_fails(self, client, sample_scheme):
        """TC-MANUAL-002: 未确认方案生成手册失败"""
        resp = client.post("/api/manual/generate", json={"scheme_id": sample_scheme.id})
        assert resp.status_code == 400
        assert "未确认" in resp.json()["detail"]

    def test_generate_not_found_scheme(self, client):
        """TC-MANUAL-003: 不存在的方案生成手册失败"""
        resp = client.post("/api/manual/generate", json={"scheme_id": 99999})
        assert resp.status_code == 404

    def test_generate_missing_scheme_id(self, client):
        """TC-MANUAL-004: 缺少 scheme_id 返回 422"""
        resp = client.post("/api/manual/generate", json={})
        assert resp.status_code == 422

    def test_generate_invalid_scheme_id_type(self, client):
        """TC-MANUAL-005: scheme_id 为字符串返回 422"""
        resp = client.post("/api/manual/generate", json={"scheme_id": "abc"})
        assert resp.status_code == 422

    def test_generate_empty_service_list(self, client, db_session):
        """TC-MANUAL-006: 空服务列表方案生成手册失败"""
        from database import GeneratedScheme
        scheme = GeneratedScheme(
            conversation_id=1, scheme_name="空方案", service_list_json="[]",
            total_cost=0, total_quote=0, status="confirmed"
        )
        db_session.add(scheme)
        db_session.commit()
        db_session.refresh(scheme)
        resp = client.post("/api/manual/generate", json={"scheme_id": scheme.id})
        assert resp.status_code == 400

    def test_generate_with_missing_template(self, client, confirmed_scheme):
        """TC-MANUAL-007: 无模板时生成手册（使用兜底内容）"""
        resp = client.post("/api/manual/generate", json={"scheme_id": confirmed_scheme.id})
        assert resp.status_code == 200
        data = resp.json()["data"]
        # 应包含 missing_templates 字段
        assert "missing_templates" in data

    def test_generate_creates_file(self, client, confirmed_scheme, sample_manual_template):
        """TC-MANUAL-008: 生成手册创建物理文件"""
        resp = client.post("/api/manual/generate", json={"scheme_id": confirmed_scheme.id})
        manual_id = resp.json()["data"]["manual_id"]

        # 查询手册路径
        get_resp = client.get(f"/api/manual/{manual_id}")
        docx_path = get_resp.json()["data"]["docx_path"]
        assert os.path.exists(docx_path)


class TestManualGet:
    """TC-MANUAL-GET: 获取手册信息"""

    def test_get_manual_exists(self, client, confirmed_scheme, sample_manual_template):
        """TC-MANUAL-009: 获取存在的手册"""
        gen_resp = client.post("/api/manual/generate", json={"scheme_id": confirmed_scheme.id})
        manual_id = gen_resp.json()["data"]["manual_id"]

        resp = client.get(f"/api/manual/{manual_id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == manual_id
        assert data["scheme_id"] == confirmed_scheme.id

    def test_get_manual_not_found(self, client):
        """TC-MANUAL-010: 获取不存在的手册，返回 404"""
        resp = client.get("/api/manual/99999")
        assert resp.status_code == 404

    def test_get_manual_invalid_id(self, client):
        """TC-MANUAL-011: 无效 ID 返回 422"""
        resp = client.get("/api/manual/abc")
        assert resp.status_code == 422


class TestManualDownload:
    """TC-MANUAL-DL: 下载手册"""

    def test_download_manual_exists(self, client, confirmed_scheme, sample_manual_template):
        """TC-MANUAL-012: 下载存在的手册文件"""
        gen_resp = client.post("/api/manual/generate", json={"scheme_id": confirmed_scheme.id})
        manual_id = gen_resp.json()["data"]["manual_id"]

        resp = client.get(f"/api/manual/{manual_id}/download")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert "service_manual_" in resp.headers.get("content-disposition", "")

    def test_download_manual_not_found(self, client):
        """TC-MANUAL-013: 下载不存在的手册，返回 404"""
        resp = client.get("/api/manual/99999/download")
        assert resp.status_code == 404

    def test_download_file_deleted(self, client, confirmed_scheme, sample_manual_template, db_session):
        """TC-MANUAL-014: 文件被删除后下载返回 404"""
        from database import GeneratedManual
        gen_resp = client.post("/api/manual/generate", json={"scheme_id": confirmed_scheme.id})
        manual_id = gen_resp.json()["data"]["manual_id"]

        manual = db_session.query(GeneratedManual).filter(GeneratedManual.id == manual_id).first()
        if manual and os.path.exists(manual.docx_path):
            os.remove(manual.docx_path)

        resp = client.get(f"/api/manual/{manual_id}/download")
        assert resp.status_code == 404
