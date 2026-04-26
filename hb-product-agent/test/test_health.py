"""
健康检查接口测试
覆盖: 正常返回、响应结构、状态码
"""


class TestHealthCheck:
    """TC-HEALTH: 健康检查"""

    def test_health_returns_200(self, client):
        """TC-HEALTH-001: /health 返回 200"""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_response_structure(self, client):
        """TC-HEALTH-002: 返回结构符合 ApiResponse 格式"""
        resp = client.get("/health")
        data = resp.json()
        assert "code" in data
        assert "message" in data
        assert "data" in data
        assert data["code"] == 0
        assert data["message"] == "success"

    def test_health_data_content(self, client):
        """TC-HEALTH-003: data 中包含 status 和 service"""
        resp = client.get("/health")
        data = resp.json()["data"]
        assert data["status"] == "ok"
        assert data["service"] == "hb-product-agent"

    def test_health_method_not_allowed(self, client):
        """TC-HEALTH-004: POST /health 返回 405"""
        resp = client.post("/health")
        assert resp.status_code == 405

    def test_health_content_type(self, client):
        """TC-HEALTH-005: Content-Type 为 application/json"""
        resp = client.get("/health")
        assert resp.headers["content-type"] == "application/json"
