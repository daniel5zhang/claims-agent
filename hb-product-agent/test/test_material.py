"""
素材库接口全量测试
覆盖: 服务列表、搜索、详情、分类、分页、边界条件
"""


class TestMaterialServices:
    """TC-MAT-SVC: 服务素材列表"""

    def test_list_services_empty_db(self, client):
        """TC-MAT-001: 空数据库返回空列表"""
        resp = client.get("/api/material/services")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_list_services_with_data(self, client, sample_services):
        """TC-MAT-002: 有数据时返回服务列表"""
        resp = client.get("/api/material/services")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == len(sample_services)
        assert data[0]["name"] == "图文问诊"

    def test_list_services_limit(self, client, sample_services):
        """TC-MAT-003: limit 参数限制返回数量"""
        resp = client.get("/api/material/services?limit=3")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 3

    def test_list_services_limit_too_large(self, client, sample_services):
        """TC-MAT-004: limit 超过最大值返回 422"""
        resp = client.get("/api/material/services?limit=999")
        assert resp.status_code == 422

    def test_list_services_limit_zero(self, client):
        """TC-MAT-005: limit=0 返回 422"""
        resp = client.get("/api/material/services?limit=0")
        assert resp.status_code == 422

    def test_list_services_keyword_match(self, client, sample_services):
        """TC-MAT-006: 关键词搜索匹配服务名"""
        resp = client.get("/api/material/services?keyword=问诊")
        assert resp.status_code == 200
        names = [s["name"] for s in resp.json()["data"]]
        assert "图文问诊" in names
        assert "视频问诊" in names

    def test_list_services_keyword_description(self, client, sample_services):
        """TC-MAT-007: 关键词搜索匹配服务描述"""
        resp = client.get("/api/material/services?keyword=三甲")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1

    def test_list_services_keyword_no_match(self, client, sample_services):
        """TC-MAT-008: 关键词无匹配返回空列表"""
        resp = client.get("/api/material/services?keyword=不存在的服务")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_list_services_category_filter(self, client, sample_services):
        """TC-MAT-009: 按类别过滤"""
        resp = client.get("/api/material/services?category=基础服务")
        assert resp.status_code == 200
        for s in resp.json()["data"]:
            assert s["category"] == "基础服务"

    def test_list_services_category_and_keyword(self, client, sample_services):
        """TC-MAT-010: 类别+关键词组合过滤"""
        resp = client.get("/api/material/services?category=增值服务&keyword=问诊")
        assert resp.status_code == 200
        # 增值服务和问诊的交集为空

    def test_list_services_response_fields(self, client, sample_services):
        """TC-MAT-011: 返回字段完整性"""
        resp = client.get("/api/material/services?limit=1")
        svc = resp.json()["data"][0]
        assert "id" in svc
        assert "category" in svc
        assert "name" in svc
        assert "description" in svc
        assert "times" in svc
        assert "cost_price" in svc


class TestMaterialServiceDetail:
    """TC-MAT-DETAIL: 服务详情"""

    def test_get_service_exists(self, client, sample_services):
        """TC-MAT-012: 获取存在的服务详情"""
        svc_id = sample_services[0].id
        resp = client.get(f"/api/material/services/{svc_id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == svc_id
        assert data["name"] == "图文问诊"
        # 详情应包含更多字段
        assert "process" in data
        assert "condition" in data
        assert "usage_rate_small" in data

    def test_get_service_not_found(self, client):
        """TC-MAT-013: 获取不存在的服务，返回 404"""
        resp = client.get("/api/material/services/99999")
        assert resp.status_code == 404

    def test_get_service_invalid_id(self, client):
        """TC-MAT-014: 无效 ID 返回 422"""
        resp = client.get("/api/material/services/abc")
        assert resp.status_code == 422

    def test_get_service_negative_id(self, client):
        """TC-MAT-015: 负数 ID 返回 422"""
        resp = client.get("/api/material/services/-1")
        assert resp.status_code == 422


class TestMaterialCategories:
    """TC-MAT-CAT: 服务类别"""

    def test_list_categories_empty(self, client):
        """TC-MAT-016: 空数据库返回空类别列表"""
        resp = client.get("/api/material/categories")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_list_categories_with_data(self, client, sample_services):
        """TC-MAT-017: 返回去重后的类别列表"""
        resp = client.get("/api/material/categories")
        assert resp.status_code == 200
        cats = resp.json()["data"]
        assert "基础服务" in cats
        assert "增值服务" in cats
        assert len(cats) == len(set(cats))  # 去重

    def test_list_categories_null_excluded(self, client, db_session):
        """TC-MAT-018: null 类别不应出现在列表中"""
        from database import Service
        db_session.add(Service(name="无类别服务", category=None))
        db_session.commit()
        resp = client.get("/api/material/categories")
        assert None not in resp.json()["data"]
